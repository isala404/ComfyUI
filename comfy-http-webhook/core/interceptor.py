"""
Output interception system for webhook delivery.
Hooks into ComfyUI's execution system to capture all outputs.

This module provides ZERO-CONFIG webhook delivery - just pass webhook_config
in extra_data via the API, and all outputs are automatically captured and sent.
No special nodes required in the workflow!

Example API request:
{
    "prompt": { /* your workflow */ },
    "extra_data": {
        "webhook_config": {
            "callback_url": "https://your-server.com/webhook",
            "auth_header": "Authorization",
            "auth_value": "Bearer your-token"
        }
    }
}
"""

import json
import logging
import threading
import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any, Callable, Optional
import uuid

try:
    from .types import WebhookContext, WebhookEvent, OutputInfo
    from .context import get_webhook_context, unregister_webhook_context, register_webhook_context
    from .client import get_webhook_client
except ImportError:
    from core.types import WebhookContext, WebhookEvent, OutputInfo
    from core.context import get_webhook_context, unregister_webhook_context, register_webhook_context
    from core.client import get_webhook_client

logger = logging.getLogger(__name__)

# Store original functions for restoration
_original_task_done = None
_interceptor_installed = False

# Thread pool for async webhook delivery (avoids event loop issues)
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="webhook_")


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
    Works with ANY workflow - no special nodes required!
    """
    global _original_task_done

    # Get prompt info BEFORE calling original (it removes from currently_running)
    prompt_tuple = self.currently_running.get(item_id)
    prompt_id = None
    extra_data = {}

    if prompt_tuple:
        # Queue item structure: (number, prompt_id, prompt, extra_data, outputs_to_execute, sensitive)
        prompt_id = prompt_tuple[1] if len(prompt_tuple) > 1 else None
        extra_data = prompt_tuple[3] if len(prompt_tuple) > 3 else {}

    # Check if this workflow has webhook config in extra_data
    webhook_config = extra_data.get("webhook_config") if isinstance(extra_data, dict) else None

    if webhook_config and prompt_id:
        # Extract outputs and send webhook in background thread
        try:
            outputs = history_result.get("outputs", {})
            meta = history_result.get("meta", {})

            # Submit webhook delivery to thread pool (avoids async/event loop issues)
            _executor.submit(
                _send_webhook_outputs_sync,
                webhook_config,
                prompt_id,
                outputs,
                meta,
                status
            )
            logger.debug(f"Webhook delivery queued for prompt {prompt_id}")

        except Exception as e:
            logger.error(f"Failed to queue webhook send: {e}")

    # Call original task_done - MUST happen for ComfyUI to work correctly
    if _original_task_done:
        return _original_task_done(self, item_id, history_result, status, process_item)


def _send_webhook_outputs_sync(
    webhook_config: dict,
    prompt_id: str,
    outputs: dict,
    meta: dict,
    status: Any
):
    """
    Send all outputs to the webhook endpoint (synchronous version for thread pool).

    Args:
        webhook_config: Webhook configuration from extra_data
        prompt_id: The prompt/execution ID
        outputs: Dictionary of node outputs
        meta: Dictionary of node metadata
        status: Execution status object
    """
    import asyncio

    # Create a new event loop for this thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(
            _send_webhook_outputs(webhook_config, prompt_id, outputs, meta, status)
        )
    except Exception as e:
        logger.error(f"Webhook delivery failed for prompt {prompt_id}: {e}\n{traceback.format_exc()}")
    finally:
        loop.close()


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
        logger.debug(f"No callback_url in webhook_config for prompt {prompt_id}, skipping")
        return

    request_id = webhook_config.get("request_id", str(uuid.uuid4()))
    start_time = datetime.now()

    try:
        # Process all outputs from all nodes
        all_outputs = process_outputs_for_webhook(outputs, meta)

        if not all_outputs:
            logger.info(f"No outputs detected for prompt {prompt_id}")
            # Still send completion event with empty outputs
            all_outputs = []

        # Enrich outputs with dimensions, file sizes
        for output in all_outputs:
            try:
                enrich_output_info(output)
            except Exception as e:
                logger.warning(f"Failed to enrich output {output.filename}: {e}")

        # Build files list for multipart
        files = []
        output_metadata = []

        for idx, output in enumerate(all_outputs):
            output_metadata.append(output.to_dict())

            # Load file content if it's a file-based output
            if output.filename:
                try:
                    file_data = load_output_file(output)
                    if file_data:
                        files.append((
                            f"file_{idx}",
                            output.filename,
                            file_data,
                            output.mime_type or "application/octet-stream"
                        ))
                except Exception as e:
                    logger.warning(f"Failed to load output file {output.filename}: {e}")

        # Extract status information
        status_str = "unknown"
        status_messages = []
        if status is not None:
            if hasattr(status, "status_str"):
                status_str = status.status_str
            elif hasattr(status, "_asdict"):
                status_dict = status._asdict()
                status_str = status_dict.get("status_str", "unknown")
                status_messages = status_dict.get("messages", [])

        # Calculate execution time from context if available
        execution_time_ms = None
        context = get_webhook_context(prompt_id)
        if context and context.start_time:
            execution_time_ms = (datetime.now() - context.start_time).total_seconds() * 1000
        else:
            # Fallback: we don't have start time, just report None
            pass

        # Build metadata payload
        metadata = {
            "event": WebhookEvent.COMPLETED.value if status_str == "success" else WebhookEvent.ERROR.value,
            "request_id": request_id,
            "prompt_id": prompt_id,
            "timestamp": datetime.now().isoformat(),
            "status": status_str,
            "outputs": output_metadata,
            "output_count": len(all_outputs),
            "file_count": len(files),
            "execution_time_ms": execution_time_ms,
            "nodes_executed": len(outputs),
        }

        # Include status messages if there are errors
        if status_messages:
            metadata["messages"] = status_messages

        # Get auth headers
        headers = _get_auth_headers(webhook_config)

        # Send the webhook
        client = get_webhook_client()

        if files:
            # Send with multipart for files
            result = await client.send_multipart(
                url=callback_url,
                metadata=metadata,
                files=files,
                headers=headers
            )
        else:
            # Send JSON only (no files, or inline content only)
            result = await client.send_json(
                url=callback_url,
                payload=metadata,
                headers=headers
            )

        if result.success:
            logger.info(
                f"Webhook delivered for prompt {prompt_id}: "
                f"{len(files)} files, {len(output_metadata)} outputs, "
                f"status={result.status}, {result.elapsed_ms:.0f}ms"
            )
        else:
            logger.error(
                f"Webhook failed for prompt {prompt_id}: "
                f"status={result.status}, error={result.error}"
            )

    except Exception as e:
        logger.error(
            f"Error sending webhook for prompt {prompt_id}: {e}\n"
            f"{traceback.format_exc()}"
        )

    finally:
        # Clean up context if it was registered
        try:
            unregister_webhook_context(prompt_id)
        except Exception:
            pass


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

    # Support additional custom headers
    custom_headers = webhook_config.get("headers")
    if isinstance(custom_headers, dict):
        headers.update(custom_headers)

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
    traceback_str: Optional[str] = None
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

    if traceback_str:
        payload["error"]["traceback"] = traceback_str[:2000]  # Truncate long tracebacks

    try:
        client = get_webhook_client()
        await client.send_json(
            url=context.callback_url,
            payload=payload,
            headers=context.get_auth_headers()
        )
    except Exception as e:
        logger.warning(f"Failed to send error event: {e}")


def shutdown():
    """Shutdown the webhook executor gracefully."""
    global _executor
    try:
        _executor.shutdown(wait=True, cancel_futures=False)
        logger.info("Webhook executor shut down")
    except Exception as e:
        logger.warning(f"Error shutting down webhook executor: {e}")
