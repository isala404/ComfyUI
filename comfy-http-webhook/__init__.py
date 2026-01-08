"""
ComfyUI HTTP Webhook Node

A production-quality custom node package for sending workflow outputs
to external HTTP webhook endpoints with support for:
- Dynamic workflow variables via API
- Real-time progress updates
- Multiple output types (image, audio, video, 3D)
- Reliable delivery with retry logic

See PLAN.md for architecture details and TODOs.md for implementation checklist.
"""

# Version
__version__ = "0.1.0"

# Node imports will be added as nodes are implemented
# from .nodes.config_node import WebhookConfig
# from .nodes.variable_nodes import (
#     WebhookStringVariable,
#     WebhookIntVariable,
#     WebhookFloatVariable,
#     WebhookBooleanVariable,
#     WebhookImageVariable,
#     WebhookSeedVariable,
# )
# from .nodes.output_nodes import (
#     WebhookImageOutput,
#     WebhookAudioOutput,
#     WebhookVideoOutput,
#     WebhookMeshOutput,
#     WebhookGenericOutput,
# )
# from .nodes.progress_node import WebhookProgressUpdate

# Node class mappings - populated as nodes are implemented
NODE_CLASS_MAPPINGS = {
    # "WebhookConfig": WebhookConfig,
    # "WebhookStringVariable": WebhookStringVariable,
    # "WebhookIntVariable": WebhookIntVariable,
    # "WebhookFloatVariable": WebhookFloatVariable,
    # "WebhookBooleanVariable": WebhookBooleanVariable,
    # "WebhookImageVariable": WebhookImageVariable,
    # "WebhookSeedVariable": WebhookSeedVariable,
    # "WebhookImageOutput": WebhookImageOutput,
    # "WebhookAudioOutput": WebhookAudioOutput,
    # "WebhookVideoOutput": WebhookVideoOutput,
    # "WebhookMeshOutput": WebhookMeshOutput,
    # "WebhookGenericOutput": WebhookGenericOutput,
    # "WebhookProgressUpdate": WebhookProgressUpdate,
}

# Display name mappings for the UI
NODE_DISPLAY_NAME_MAPPINGS = {
    # "WebhookConfig": "Webhook Config",
    # "WebhookStringVariable": "Webhook String Variable",
    # "WebhookIntVariable": "Webhook Int Variable",
    # "WebhookFloatVariable": "Webhook Float Variable",
    # "WebhookBooleanVariable": "Webhook Boolean Variable",
    # "WebhookImageVariable": "Webhook Image Variable",
    # "WebhookSeedVariable": "Webhook Seed Variable",
    # "WebhookImageOutput": "Webhook Image Output",
    # "WebhookAudioOutput": "Webhook Audio Output",
    # "WebhookVideoOutput": "Webhook Video Output",
    # "WebhookMeshOutput": "Webhook Mesh Output",
    # "WebhookGenericOutput": "Webhook Generic Output",
    # "WebhookProgressUpdate": "Webhook Progress Update",
}

# Print confirmation on load
print(f"[comfy-http-webhook] Loaded v{__version__} - See PLAN.md and TODOs.md for implementation status")
