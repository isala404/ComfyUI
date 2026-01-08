"""
WebhookInput nodes - Extract specific inputs from webhook context.
"""

import asyncio
import json
import logging
from typing import Any

import torch

try:
    from ..core.types import WebhookContext
    from ..processors.inputs import WebhookInputProcessor
except ImportError:
    from core.types import WebhookContext
    from processors.inputs import WebhookInputProcessor

logger = logging.getLogger(__name__)

# Shared processor instance
_processor = None


def get_processor() -> WebhookInputProcessor:
    """Get or create the shared input processor."""
    global _processor
    if _processor is None:
        _processor = WebhookInputProcessor()
    return _processor


def _run_async(coro):
    """Run an async coroutine in sync context."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Create a new loop in a thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, coro)
                return future.result()
        else:
            return loop.run_until_complete(coro)
    except RuntimeError:
        # No event loop, create one
        return asyncio.run(coro)


class WebhookTextInput:
    """Extract text input from webhook context."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "webhook_context": ("WEBHOOK_CONTEXT",),
                "input_name": ("STRING", {
                    "default": "prompt",
                    "tooltip": "Name of the input variable to extract"
                }),
            },
            "optional": {
                "default_value": ("STRING", {
                    "default": "",
                    "multiline": True,
                    "tooltip": "Default value if input is not provided"
                }),
            },
        }

    RETURN_TYPES = ("STRING",)
    FUNCTION = "extract"
    CATEGORY = "webhook/inputs"
    DESCRIPTION = "Extract a text string from webhook inputs."

    def extract(self, webhook_context, input_name, default_value=""):
        if not isinstance(webhook_context, WebhookContext):
            return (default_value,)

        value = webhook_context.get_input(input_name, default_value)
        return (str(value),)


class WebhookTextsInput:
    """Extract multiple text inputs as a list."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "webhook_context": ("WEBHOOK_CONTEXT",),
                "input_name": ("STRING", {
                    "default": "prompts",
                    "tooltip": "Name of the input array to extract"
                }),
            },
        }

    RETURN_TYPES = ("STRING",)
    OUTPUT_IS_LIST = (True,)
    FUNCTION = "extract"
    CATEGORY = "webhook/inputs"
    DESCRIPTION = "Extract multiple text strings from webhook inputs as a list."

    def extract(self, webhook_context, input_name):
        if not isinstance(webhook_context, WebhookContext):
            return ([],)

        values = webhook_context.get_input(input_name, [])
        if isinstance(values, str):
            values = [values]
        elif not isinstance(values, list):
            values = [str(values)]
        else:
            values = [str(v) for v in values]

        return (values,)


class WebhookIntInput:
    """Extract integer from webhook context."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "webhook_context": ("WEBHOOK_CONTEXT",),
                "input_name": ("STRING", {
                    "default": "seed",
                    "tooltip": "Name of the input variable to extract"
                }),
            },
            "optional": {
                "default_value": ("INT", {
                    "default": 0,
                    "tooltip": "Default value if input is not provided"
                }),
            },
        }

    RETURN_TYPES = ("INT",)
    FUNCTION = "extract"
    CATEGORY = "webhook/inputs"
    DESCRIPTION = "Extract an integer from webhook inputs."

    def extract(self, webhook_context, input_name, default_value=0):
        if not isinstance(webhook_context, WebhookContext):
            return (default_value,)

        value = webhook_context.get_input(input_name, default_value)
        try:
            return (int(value),)
        except (ValueError, TypeError):
            return (default_value,)


class WebhookFloatInput:
    """Extract float from webhook context."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "webhook_context": ("WEBHOOK_CONTEXT",),
                "input_name": ("STRING", {
                    "default": "cfg",
                    "tooltip": "Name of the input variable to extract"
                }),
            },
            "optional": {
                "default_value": ("FLOAT", {
                    "default": 7.0,
                    "tooltip": "Default value if input is not provided"
                }),
            },
        }

    RETURN_TYPES = ("FLOAT",)
    FUNCTION = "extract"
    CATEGORY = "webhook/inputs"
    DESCRIPTION = "Extract a float from webhook inputs."

    def extract(self, webhook_context, input_name, default_value=7.0):
        if not isinstance(webhook_context, WebhookContext):
            return (default_value,)

        value = webhook_context.get_input(input_name, default_value)
        try:
            return (float(value),)
        except (ValueError, TypeError):
            return (default_value,)


class WebhookBoolInput:
    """Extract boolean from webhook context."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "webhook_context": ("WEBHOOK_CONTEXT",),
                "input_name": ("STRING", {
                    "default": "use_hires",
                    "tooltip": "Name of the input variable to extract"
                }),
            },
            "optional": {
                "default_value": ("BOOLEAN", {
                    "default": False,
                    "tooltip": "Default value if input is not provided"
                }),
            },
        }

    RETURN_TYPES = ("BOOLEAN",)
    FUNCTION = "extract"
    CATEGORY = "webhook/inputs"
    DESCRIPTION = "Extract a boolean from webhook inputs."

    def extract(self, webhook_context, input_name, default_value=False):
        if not isinstance(webhook_context, WebhookContext):
            return (default_value,)

        value = webhook_context.get_input(input_name, default_value)

        # Handle various boolean representations
        if isinstance(value, bool):
            return (value,)
        if isinstance(value, str):
            return (value.lower() in ("true", "1", "yes", "on"),)
        return (bool(value),)


class WebhookImageInput:
    """Extract single image from webhook context."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "webhook_context": ("WEBHOOK_CONTEXT",),
                "input_name": ("STRING", {
                    "default": "image",
                    "tooltip": "Name of the image input (base64 or URL)"
                }),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "extract"
    CATEGORY = "webhook/inputs"
    DESCRIPTION = "Extract an image from webhook inputs (base64 or URL)."

    def extract(self, webhook_context, input_name):
        if not isinstance(webhook_context, WebhookContext):
            return (torch.zeros(1, 64, 64, 3),)

        value = webhook_context.get_input(input_name)
        if value is None:
            return (torch.zeros(1, 64, 64, 3),)

        processor = get_processor()
        try:
            tensor = _run_async(processor.process_image(value))
            return (tensor,)
        except Exception as e:
            logger.error(f"Failed to process image input '{input_name}': {e}")
            return (torch.zeros(1, 64, 64, 3),)


class WebhookImagesInput:
    """Extract multiple images as batched tensor."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "webhook_context": ("WEBHOOK_CONTEXT",),
                "input_name": ("STRING", {
                    "default": "images",
                    "tooltip": "Name of the images array input"
                }),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "extract"
    CATEGORY = "webhook/inputs"
    DESCRIPTION = "Extract multiple images as a batched tensor."

    def extract(self, webhook_context, input_name):
        if not isinstance(webhook_context, WebhookContext):
            return (torch.zeros(1, 64, 64, 3),)

        values = webhook_context.get_input(input_name, [])
        if not values:
            return (torch.zeros(1, 64, 64, 3),)

        if not isinstance(values, list):
            values = [values]

        processor = get_processor()
        try:
            async def process_all():
                tensors = []
                for value in values:
                    tensor = await processor.process_image(value)
                    tensors.append(tensor)
                return processor._batch_images(tensors)

            batched = _run_async(process_all())
            return (batched,)
        except Exception as e:
            logger.error(f"Failed to process images input '{input_name}': {e}")
            return (torch.zeros(1, 64, 64, 3),)


class WebhookAudioInput:
    """Extract audio from webhook context."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "webhook_context": ("WEBHOOK_CONTEXT",),
                "input_name": ("STRING", {
                    "default": "audio",
                    "tooltip": "Name of the audio input (base64 or URL)"
                }),
            },
        }

    RETURN_TYPES = ("AUDIO",)
    FUNCTION = "extract"
    CATEGORY = "webhook/inputs"
    DESCRIPTION = "Extract audio from webhook inputs (base64 or URL)."

    def extract(self, webhook_context, input_name):
        default_audio = {"waveform": torch.zeros(1, 1, 44100), "sample_rate": 44100}

        if not isinstance(webhook_context, WebhookContext):
            return (default_audio,)

        value = webhook_context.get_input(input_name)
        if value is None:
            return (default_audio,)

        processor = get_processor()
        try:
            audio = _run_async(processor.process_audio(value))
            return (audio,)
        except Exception as e:
            logger.error(f"Failed to process audio input '{input_name}': {e}")
            return (default_audio,)


class WebhookMaskInput:
    """Extract mask from webhook context."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "webhook_context": ("WEBHOOK_CONTEXT",),
                "input_name": ("STRING", {
                    "default": "mask",
                    "tooltip": "Name of the mask input (grayscale image)"
                }),
            },
        }

    RETURN_TYPES = ("MASK",)
    FUNCTION = "extract"
    CATEGORY = "webhook/inputs"
    DESCRIPTION = "Extract a mask from webhook inputs (grayscale image)."

    def extract(self, webhook_context, input_name):
        if not isinstance(webhook_context, WebhookContext):
            return (torch.zeros(1, 64, 64),)

        value = webhook_context.get_input(input_name)
        if value is None:
            return (torch.zeros(1, 64, 64),)

        processor = get_processor()
        try:
            mask = _run_async(processor.process_mask(value))
            return (mask,)
        except Exception as e:
            logger.error(f"Failed to process mask input '{input_name}': {e}")
            return (torch.zeros(1, 64, 64),)


class WebhookVideoInput:
    """Extract video from webhook context."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "webhook_context": ("WEBHOOK_CONTEXT",),
                "input_name": ("STRING", {
                    "default": "video",
                    "tooltip": "Name of the video input (base64 or URL)"
                }),
            },
        }

    RETURN_TYPES = ("VIDEO",)
    FUNCTION = "extract"
    CATEGORY = "webhook/inputs"
    DESCRIPTION = "Extract video from webhook inputs (base64 or URL)."

    def extract(self, webhook_context, input_name):
        if not isinstance(webhook_context, WebhookContext):
            return (None,)

        value = webhook_context.get_input(input_name)
        if value is None:
            return (None,)

        processor = get_processor()
        try:
            video = _run_async(processor.process_video(value))
            return (video,)
        except Exception as e:
            logger.error(f"Failed to process video input '{input_name}': {e}")
            return (None,)


class WebhookJSONInput:
    """Extract JSON data as string from webhook context."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "webhook_context": ("WEBHOOK_CONTEXT",),
                "input_name": ("STRING", {
                    "default": "params",
                    "tooltip": "Name of the JSON object input"
                }),
            },
        }

    RETURN_TYPES = ("STRING",)
    FUNCTION = "extract"
    CATEGORY = "webhook/inputs"
    DESCRIPTION = "Extract JSON data from webhook inputs as a string."

    def extract(self, webhook_context, input_name):
        if not isinstance(webhook_context, WebhookContext):
            return ("{}",)

        value = webhook_context.get_input(input_name, {})
        if isinstance(value, dict):
            return (json.dumps(value),)
        elif isinstance(value, str):
            # Already a string, validate it's JSON
            try:
                json.loads(value)
                return (value,)
            except json.JSONDecodeError:
                return (json.dumps({"value": value}),)
        else:
            return (json.dumps({"value": value}),)


class WebhookAnyInput:
    """Extract any input type from webhook context."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "webhook_context": ("WEBHOOK_CONTEXT",),
                "input_name": ("STRING", {
                    "default": "data",
                    "tooltip": "Name of the input variable to extract"
                }),
            },
        }

    RETURN_TYPES = ("*",)
    FUNCTION = "extract"
    CATEGORY = "webhook/inputs"
    DESCRIPTION = "Extract any type of input from webhook inputs."

    def extract(self, webhook_context, input_name):
        if not isinstance(webhook_context, WebhookContext):
            return (None,)

        value = webhook_context.get_input(input_name)
        return (value,)
