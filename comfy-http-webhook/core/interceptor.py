"""
Output interception system for webhook delivery.
Hooks into ComfyUI's execution system to capture all outputs.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Callable, Optional
import uuid

from .types import WebhookContext, WebhookEvent, OutputInfo
from .context import get_webhook_context, unregister_webhook_context
from .client import get_webhook_client

logger = logging.getLogger(__name__)

# Store original functions for restoration
_original_task_done = None
_interceptor_installed = False


def install_output_interceptor() -> bool:
    """
    Install the output interceptor hook into ComfyUI's execution system.

    Returns:
        True if installation succeeded, False otherwise
    """
    global _original_task_done, _interceptor_installed

    if _interceptor_installed:
        logger.debug("Output interceptor already installed")
        return True

    try:
        import execution

        # Store original task_done method
        _original_task_done = execution.PromptQueue.task_done

        # Replace with our interceptor
        execution.PromptQueue.task_done = _intercepted_task_done

        _interceptor_installed = True
        logger.info("Webhook output interceptor installed successfully")
        return True

    except ImportError as e:
        logger.error(f"Failed to import execution module: {e}")
        return False
    except Exception as e:
        logger.error(f"Failed to install output interceptor: {e}")
        return False


def uninstall_output_interceptor() -> bool:
    """
    Uninstall the output interceptor and restore original behavior.

    Returns:
        True if uninstallation succeeded, False otherwise
    """
    global _original_task_done, _interceptor_installed

    if not _interceptor_installed:
        logger.debug("Output interceptor not installed")
        return True

    try:
        import execution

        if _original_task_done is not None:
            execution.PromptQueue.task_done = _original_task_done
            _original_task_done = None

        _interceptor_installed = False
        logger.info("Webhook output interceptor uninstalled")
        return True

    except Exception as e:
        logger.error(f"Failed to uninstall output interceptor: {e}")
        return False


def _intercepted_task_done(
    self,
    item_id: Any,
    history_result: dict,
    status: Any,
    process_item: Optional[Callable] = None
):
    """
    Intercepted task_done method that sends webhook outputs.

    This is called when a workflow execution completes.
    """
    global _original_task_done

    # Get prompt info before calling original (it removes from currently_running)
    prompt = self.currently_running.get(item_id)
    prompt_id = None
    extra_data = {}

    if prompt:
        prompt_id = prompt[1] if len(prompt) > 1 else None
        extra_data = prompt[3] if len(prompt) > 3 else {}

    # Check if this workflow has webhook config
    webhook_config = extra_data.get("webhook_config")

    if webhook_config and prompt_id:
        # Extract outputs and send webhook
        try:
            outputs = history_result.get("outputs", {})
            meta = history_result.get("meta", {})

            # Fire webhook asynchronously
            asyncio.create_task(
                _send_webhook_outputs(
                    webhook_config,
                    prompt_id,
                    outputs,
                    meta,
                    status
                )
            )
        except Exception as e:
            logger.error(f"Failed to trigger webhook send: {e}")

    # Call original task_done
    if _original_task_done:
        return _original_task_done(self, item_id, history_result, status, process_item)


async def _send_webhook_outputs(
    webhook_config: dict,
    prompt_id: str,
    outputs: dict,
    meta: dict,
    status: Any
):
    """
    Send all outputs to the webhook endpoint.

    Args:
        webhook_config: Webhook configuration from extra_data
        prompt_id: The prompt/execution ID
        outputs: Dictionary of node outputs
        meta: Dictionary of node metadata
        status: Execution status object
    """
    try:
        from ..processors.outputs import (
            process_outputs_for_webhook,
            load_output_file,
            enrich_output_info
        )
    except ImportError:
        from processors.outputs import (
            process_outputs_for_webhook,
            load_output_file,
            enrich_output_info
        )

    callback_url = webhook_config.get("callback_url")
    if not callback_url:
        logger.warning("No callback_url in webhook_config, skipping webhook")
        return

    request_id = webhook_config.get("request_id", str(uuid.uuid4()))

    try:
        # Process all outputs
        all_outputs = process_outputs_for_webhook(outputs, meta)

        # Enrich with dimensions, file sizes
        for output in all_outputs:
            enrich_output_info(output)

        # Build files list for multipart
        files = []
        output_metadata = []

        for idx, output in enumerate(all_outputs):
            output_metadata.append(output.to_dict())

            # Load file content if it's a file-based output
            if output.filename:
                file_data = load_output_file(output)
                if file_data:
                    files.append((
                        f"file_{idx}",
                        output.filename,
                        file_data,
                        output.mime_type
                    ))

        # Build metadata payload
        status_str = "unknown"
        if status is not None:
            if hasattr(status, "status_str"):
                status_str = status.status_str
            elif hasattr(status, "_asdict"):
                status_dict = status._asdict()
                status_str = status_dict.get("status_str", "unknown")

        # Calculate execution time
        context = get_webhook_context(prompt_id)
        execution_time_ms = None
        if context and context.start_time:
            execution_time_ms = (datetime.now() - context.start_time).total_seconds() * 1000

        metadata = {
            "event": WebhookEvent.OUTPUT_BATCH.value,
            "request_id": request_id,
            "prompt_id": prompt_id,
            "timestamp": datetime.now().isoformat(),
            "status": status_str,
            "outputs": output_metadata,
            "execution_time_ms": execution_time_ms,
            "nodes_executed": len(outputs),
        }

        # Get auth headers
        headers = _get_auth_headers(webhook_config)

        # Send multipart request
        client = get_webhook_client()

        if files:
            result = await client.send_multipart(
                url=callback_url,
                metadata=metadata,
                files=files,
                headers=headers
            )
        else:
            # No files, send JSON only
            result = await client.send_json(
                url=callback_url,
                payload=metadata,
                headers=headers
            )

        if result.success:
            logger.info(
                f"Webhook sent successfully for prompt {prompt_id}: "
                f"{len(files)} files, {result.elapsed_ms:.0f}ms"
            )
        else:
            logger.error(
                f"Webhook failed for prompt {prompt_id}: {result.error}"
            )

    except Exception as e:
        logger.error(f"Error sending webhook for prompt {prompt_id}: {e}", exc_info=True)

    finally:
        # Clean up context
        unregister_webhook_context(prompt_id)


def _get_auth_headers(webhook_config: dict) -> dict:
    """
    Build authentication headers from webhook config.

    Args:
        webhook_config: Configuration dictionary

    Returns:
        Headers dictionary
    """
    headers = {}

    auth_header = webhook_config.get("auth_header")
    auth_value = webhook_config.get("auth_value")

    if auth_header and auth_value:
        headers[auth_header] = auth_value

    return headers


async def send_progress_event(
    context: WebhookContext,
    node_id: str,
    node_type: str,
    progress: float,
    message: str = ""
):
    """
    Send a progress event to the webhook endpoint.

    Args:
        context: The webhook context
        node_id: Current node being executed
        node_type: Type of the node
        progress: Progress value 0-1
        message: Optional progress message
    """
    if not context.send_progress or not context.callback_url:
        return

    elapsed_ms = None
    if context.start_time:
        elapsed_ms = (datetime.now() - context.start_time).total_seconds() * 1000

    payload = {
        "event": WebhookEvent.PROGRESS.value,
        "request_id": context.request_id,
        "prompt_id": context.prompt_id,
        "timestamp": datetime.now().isoformat(),
        "node_id": node_id,
        "node_type": node_type,
        "progress": progress,
        "message": message,
        "elapsed_ms": elapsed_ms,
    }

    try:
        client = get_webhook_client()
        result = await client.send_json(
            url=context.callback_url,
            payload=payload,
            headers=context.get_auth_headers()
        )

        if not result.success:
            logger.warning(f"Progress event failed: {result.error}")

    except Exception as e:
        logger.warning(f"Failed to send progress event: {e}")


async def send_started_event(context: WebhookContext):
    """Send workflow started event."""
    if not context.callback_url:
        return

    payload = {
        "event": WebhookEvent.STARTED.value,
        "request_id": context.request_id,
        "prompt_id": context.prompt_id,
        "timestamp": datetime.now().isoformat(),
    }

    try:
        client = get_webhook_client()
        await client.send_json(
            url=context.callback_url,
            payload=payload,
            headers=context.get_auth_headers()
        )
    except Exception as e:
        logger.warning(f"Failed to send started event: {e}")


async def send_error_event(
    context: WebhookContext,
    error_type: str,
    error_message: str,
    node_id: Optional[str] = None,
    node_type: Optional[str] = None,
    traceback: Optional[str] = None
):
    """Send workflow error event."""
    if not context.callback_url:
        return

    elapsed_ms = None
    if context.start_time:
        elapsed_ms = (datetime.now() - context.start_time).total_seconds() * 1000

    payload = {
        "event": WebhookEvent.ERROR.value,
        "request_id": context.request_id,
        "prompt_id": context.prompt_id,
        "timestamp": datetime.now().isoformat(),
        "error": {
            "type": error_type,
            "message": error_message,
            "node_id": node_id,
            "node_type": node_type,
        },
        "elapsed_ms": elapsed_ms,
    }

    if traceback:
        payload["error"]["traceback"] = traceback[:2000]  # Truncate long tracebacks

    try:
        client = get_webhook_client()
        await client.send_json(
            url=context.callback_url,
            payload=payload,
            headers=context.get_auth_headers()
        )
    except Exception as e:
        logger.warning(f"Failed to send error event: {e}")
