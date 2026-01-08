"""
ComfyUI HTTP Webhook Node

A production-quality custom node package for sending workflow outputs
to external HTTP webhook endpoints with support for:
- Dynamic workflow variables via API (text, images, audio, video, masks)
- Real-time progress updates
- Multiple output types (image, audio, video, 3D mesh)
- Reliable delivery with retry logic and multipart support
- Universal output interception (works with built-in and custom nodes)

See PLAN.md for architecture details and TODOs.md for implementation checklist.

Usage:
1. Add WebhookReceiver to your workflow as the entry point
2. Connect WebhookInput nodes to extract variables
3. Connect to your regular workflow nodes (KSampler, VAE, etc.)
4. Use standard output nodes (SaveImage, SaveAudio) - outputs are auto-intercepted
5. Submit via API with webhook_config and webhook_inputs in extra_data

Example API request:
{
    "prompt": { /* workflow */ },
    "extra_data": {
        "webhook_config": {
            "callback_url": "https://api.example.com/webhook",
            "auth_header": "Authorization",
            "auth_value": "Bearer token123",
            "request_id": "req_abc123"
        },
        "webhook_inputs": {
            "prompt": "a beautiful sunset",
            "seed": 42,
            "image": "data:image/png;base64,..."
        }
    }
}
"""

__version__ = "0.1.0"

import logging

# Configure logging
logger = logging.getLogger(__name__)

# Import nodes
from .nodes.receiver import WebhookReceiver, WebhookDebugInfo
from .nodes.inputs import (
    WebhookTextInput,
    WebhookTextsInput,
    WebhookIntInput,
    WebhookFloatInput,
    WebhookBoolInput,
    WebhookImageInput,
    WebhookImagesInput,
    WebhookAudioInput,
    WebhookMaskInput,
    WebhookVideoInput,
    WebhookJSONInput,
    WebhookAnyInput,
)
from .nodes.send import WebhookSend, WebhookSendJSON

# Import core components for advanced usage
from .core.types import WebhookContext, WebhookResult, OutputInfo, WebhookEvent
from .core.context import (
    register_webhook_context,
    get_webhook_context,
    unregister_webhook_context,
)
from .core.interceptor import install_output_interceptor, uninstall_output_interceptor
from .core.client import WebhookClient, get_webhook_client


# Node class mappings for ComfyUI
NODE_CLASS_MAPPINGS = {
    # Entry point
    "WebhookReceiver": WebhookReceiver,
    "WebhookDebugInfo": WebhookDebugInfo,

    # Input extraction nodes
    "WebhookTextInput": WebhookTextInput,
    "WebhookTextsInput": WebhookTextsInput,
    "WebhookIntInput": WebhookIntInput,
    "WebhookFloatInput": WebhookFloatInput,
    "WebhookBoolInput": WebhookBoolInput,
    "WebhookImageInput": WebhookImageInput,
    "WebhookImagesInput": WebhookImagesInput,
    "WebhookAudioInput": WebhookAudioInput,
    "WebhookMaskInput": WebhookMaskInput,
    "WebhookVideoInput": WebhookVideoInput,
    "WebhookJSONInput": WebhookJSONInput,
    "WebhookAnyInput": WebhookAnyInput,

    # Output nodes
    "WebhookSend": WebhookSend,
    "WebhookSendJSON": WebhookSendJSON,
}

# Display name mappings for the UI
NODE_DISPLAY_NAME_MAPPINGS = {
    # Entry point
    "WebhookReceiver": "Webhook Receiver",
    "WebhookDebugInfo": "Webhook Debug Info",

    # Input extraction nodes
    "WebhookTextInput": "Webhook Text Input",
    "WebhookTextsInput": "Webhook Texts Input (List)",
    "WebhookIntInput": "Webhook Int Input",
    "WebhookFloatInput": "Webhook Float Input",
    "WebhookBoolInput": "Webhook Bool Input",
    "WebhookImageInput": "Webhook Image Input",
    "WebhookImagesInput": "Webhook Images Input (Batch)",
    "WebhookAudioInput": "Webhook Audio Input",
    "WebhookMaskInput": "Webhook Mask Input",
    "WebhookVideoInput": "Webhook Video Input",
    "WebhookJSONInput": "Webhook JSON Input",
    "WebhookAnyInput": "Webhook Any Input",

    # Output nodes
    "WebhookSend": "Webhook Send",
    "WebhookSendJSON": "Webhook Send JSON",
}

# Category for all nodes
WEB_DIRECTORY = None


def _init_webhook_system():
    """Initialize the webhook system on module load."""
    try:
        # Install the output interceptor
        success = install_output_interceptor()
        if success:
            logger.info(f"[comfy-http-webhook] v{__version__} loaded successfully")
        else:
            logger.warning(
                f"[comfy-http-webhook] v{__version__} loaded but interceptor "
                "installation failed - output capture may not work"
            )
    except Exception as e:
        logger.error(f"[comfy-http-webhook] Failed to initialize: {e}")


# Initialize on import
_init_webhook_system()

# Export public API
__all__ = [
    # Version
    "__version__",

    # Nodes
    "WebhookReceiver",
    "WebhookDebugInfo",
    "WebhookTextInput",
    "WebhookTextsInput",
    "WebhookIntInput",
    "WebhookFloatInput",
    "WebhookBoolInput",
    "WebhookImageInput",
    "WebhookImagesInput",
    "WebhookAudioInput",
    "WebhookMaskInput",
    "WebhookVideoInput",
    "WebhookJSONInput",
    "WebhookAnyInput",
    "WebhookSend",
    "WebhookSendJSON",

    # Core types
    "WebhookContext",
    "WebhookResult",
    "OutputInfo",
    "WebhookEvent",

    # Context management
    "register_webhook_context",
    "get_webhook_context",
    "unregister_webhook_context",

    # Interceptor
    "install_output_interceptor",
    "uninstall_output_interceptor",

    # Client
    "WebhookClient",
    "get_webhook_client",

    # ComfyUI mappings
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
]
