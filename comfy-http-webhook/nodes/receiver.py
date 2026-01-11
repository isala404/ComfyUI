"""
WebhookReceiver node - Entry point for webhook-triggered workflows.
Extracts configuration and all input variables from extra_data.
"""

import asyncio
import logging
import uuid
from datetime import datetime

try:
    from ..core.types import WebhookContext
    from ..core.context import register_webhook_context
    from ..core.interceptor import send_started_event
except ImportError:
    from core.types import WebhookContext
    from core.context import register_webhook_context
    from core.interceptor import send_started_event

logger = logging.getLogger(__name__)


class WebhookReceiver:
    """
    Entry point for webhook-triggered workflows.

    This node extracts webhook configuration and input variables from
    the extra_data passed via the API. It creates a WebhookContext
    that is passed through the workflow and used for output interception.

    Usage:
    1. Add WebhookReceiver to your workflow
    2. Connect its output to WebhookInput nodes
    3. Submit workflow via API with webhook_config and webhook_inputs in extra_data
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {},
            "optional": {
                "default_callback_url": ("STRING", {
                    "default": "",
                    "tooltip": "Default callback URL if not provided in API request"
                }),
                "default_timeout": ("INT", {
                    "default": 60,
                    "min": 1,
                    "max": 300,
                    "tooltip": "Default timeout in seconds for webhook requests"
                }),
                "default_max_retries": ("INT", {
                    "default": 3,
                    "min": 0,
                    "max": 10,
                    "tooltip": "Default maximum retry attempts for failed requests"
                }),
            },
            "hidden": {
                "prompt": "PROMPT",
                "extra_pnginfo": "EXTRA_PNGINFO",
                "unique_id": "UNIQUE_ID",
            },
        }

    RETURN_TYPES = ("WEBHOOK_CONTEXT",)
    RETURN_NAMES = ("webhook_context",)
    FUNCTION = "receive"
    CATEGORY = "webhook"
    DESCRIPTION = "Entry point for webhook-triggered workflows. Extracts configuration and inputs from API request."

    def receive(
        self,
        prompt=None,
        extra_pnginfo=None,
        unique_id=None,
        default_callback_url="",
        default_timeout=60,
        default_max_retries=3,
    ):
        """
        Extract webhook configuration and create context.

        The context is registered for output interception and passed
        to WebhookInput nodes for variable extraction.
        """
        # Extract webhook_config and webhook_inputs from extra_data
        extra_data = extra_pnginfo or {}
        webhook_config = extra_data.get("webhook_config", {})
        webhook_inputs = extra_data.get("webhook_inputs", {})

        # Build context with config values or defaults
        callback_url = webhook_config.get("callback_url", default_callback_url)
        request_id = webhook_config.get("request_id", str(uuid.uuid4()))

        context = WebhookContext(
            callback_url=callback_url,
            request_id=request_id,
            auth_header=webhook_config.get("auth_header"),
            auth_value=webhook_config.get("auth_value"),
            send_progress=webhook_config.get("send_progress", True),
            progress_interval_ms=webhook_config.get("progress_interval_ms", 1000),
            timeout=webhook_config.get("timeout_seconds", default_timeout),
            max_retries=webhook_config.get("max_retries", default_max_retries),
            inputs=webhook_inputs,
            prompt_id=unique_id,
            include_workflow_in_response=webhook_config.get("include_workflow_in_response", False),
            start_time=datetime.now(),
        )

        # Register context for output interception
        if context.prompt_id:
            register_webhook_context(context)
            logger.info(
                f"WebhookReceiver: Registered context for prompt {context.prompt_id}, "
                f"callback: {callback_url or '(none)'}, "
                f"inputs: {list(webhook_inputs.keys())}"
            )

            # Send started event if callback URL is configured
            if context.callback_url:
                try:
                    # Run async event in sync context
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        asyncio.create_task(send_started_event(context))
                    else:
                        loop.run_until_complete(send_started_event(context))
                except Exception as e:
                    logger.warning(f"Failed to send started event: {e}")

        return (context,)


class WebhookDebugInfo:
    """
    Debug node that outputs webhook context information as text.
    Useful for troubleshooting webhook configurations.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "webhook_context": ("WEBHOOK_CONTEXT",),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("debug_info",)
    FUNCTION = "get_info"
    CATEGORY = "webhook/debug"
    DESCRIPTION = "Outputs debug information about the webhook context."

    def get_info(self, webhook_context):
        """Extract and format debug information from context."""
        if not isinstance(webhook_context, WebhookContext):
            return ("Invalid webhook context",)

        info_lines = [
            "=== Webhook Debug Info ===",
            f"Request ID: {webhook_context.request_id}",
            f"Prompt ID: {webhook_context.prompt_id}",
            f"Callback URL: {webhook_context.callback_url or '(not set)'}",
            f"Auth Header: {webhook_context.auth_header or '(not set)'}",
            f"Auth Value: {'(set)' if webhook_context.auth_value else '(not set)'}",
            f"Send Progress: {webhook_context.send_progress}",
            f"Timeout: {webhook_context.timeout}s",
            f"Max Retries: {webhook_context.max_retries}",
            "",
            "=== Inputs ===",
        ]

        for key, value in webhook_context.inputs.items():
            # Truncate long values
            str_value = str(value)
            if len(str_value) > 100:
                str_value = str_value[:100] + "..."
            info_lines.append(f"  {key}: {str_value}")

        if not webhook_context.inputs:
            info_lines.append("  (no inputs)")

        return ("\n".join(info_lines),)
