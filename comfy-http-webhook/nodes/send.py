"""
WebhookSend node - Manually send data to webhook.
"""

import asyncio
import io
import json
import logging
from datetime import datetime
from typing import Optional

import numpy as np
import torch
from PIL import Image

try:
    from ..core.types import WebhookContext, WebhookEvent, OutputInfo
    from ..core.client import get_webhook_client
    from ..utils.mime import guess_mime_type
except ImportError:
    from core.types import WebhookContext, WebhookEvent, OutputInfo
    from core.client import get_webhook_client
    from utils.mime import guess_mime_type

logger = logging.getLogger(__name__)


def _run_async(coro):
    """Run an async coroutine in sync context."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, coro)
                return future.result()
        else:
            return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


class WebhookSend:
    """
    Manually send data to webhook endpoint.

    Use this when you need to send outputs that aren't captured by
    standard output nodes, or when you want more control over what
    gets sent.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "webhook_context": ("WEBHOOK_CONTEXT",),
            },
            "optional": {
                "images": ("IMAGE", {
                    "tooltip": "Images to send (batched tensor)"
                }),
                "audio": ("AUDIO", {
                    "tooltip": "Audio to send"
                }),
                "text": ("STRING", {
                    "default": "",
                    "multiline": True,
                    "tooltip": "Text content to send"
                }),
                "json_data": ("STRING", {
                    "default": "",
                    "multiline": True,
                    "tooltip": "JSON string to include in metadata"
                }),
                "custom_event": ("STRING", {
                    "default": "",
                    "tooltip": "Custom event type (default: output.manual)"
                }),
            },
        }

    RETURN_TYPES = ()
    OUTPUT_NODE = True
    FUNCTION = "send"
    CATEGORY = "webhook"
    DESCRIPTION = "Manually send data to the webhook endpoint."

    def send(
        self,
        webhook_context,
        images=None,
        audio=None,
        text="",
        json_data="",
        custom_event="",
    ):
        if not isinstance(webhook_context, WebhookContext):
            logger.warning("WebhookSend: Invalid webhook context")
            return {}

        if not webhook_context.callback_url:
            logger.warning("WebhookSend: No callback URL configured")
            return {}

        try:
            result = _run_async(
                self._send_async(
                    webhook_context,
                    images,
                    audio,
                    text,
                    json_data,
                    custom_event
                )
            )
            return {}
        except Exception as e:
            logger.error(f"WebhookSend failed: {e}", exc_info=True)
            return {}

    async def _send_async(
        self,
        context: WebhookContext,
        images: Optional[torch.Tensor],
        audio: Optional[dict],
        text: str,
        json_data: str,
        custom_event: str,
    ):
        """Async implementation of send."""
        files = []
        outputs = []

        # Process images
        if images is not None:
            image_files = self._process_images(images)
            for idx, (filename, data, mime_type) in enumerate(image_files):
                files.append((f"image_{idx}", filename, data, mime_type))
                outputs.append(OutputInfo(
                    type="image",
                    filename=filename,
                    mime_type=mime_type,
                    file_size_bytes=len(data),
                ).to_dict())

        # Process audio
        if audio is not None:
            audio_data = self._process_audio(audio)
            if audio_data:
                filename, data, mime_type = audio_data
                files.append(("audio_0", filename, data, mime_type))
                outputs.append(OutputInfo(
                    type="audio",
                    filename=filename,
                    mime_type=mime_type,
                    file_size_bytes=len(data),
                    sample_rate=audio.get("sample_rate", 44100),
                ).to_dict())

        # Process text
        if text:
            outputs.append(OutputInfo(
                type="text",
                inline_content=text,
                mime_type="text/plain",
            ).to_dict())

        # Parse custom JSON data
        custom_metadata = {}
        if json_data:
            try:
                custom_metadata = json.loads(json_data)
            except json.JSONDecodeError:
                logger.warning("WebhookSend: Invalid JSON data, ignoring")

        # Build metadata
        event_type = custom_event or "output.manual"
        metadata = {
            "event": event_type,
            "request_id": context.request_id,
            "prompt_id": context.prompt_id,
            "timestamp": datetime.now().isoformat(),
            "outputs": outputs,
            "custom_metadata": custom_metadata,
        }

        # Send request
        client = get_webhook_client()

        if files:
            result = await client.send_multipart(
                url=context.callback_url,
                metadata=metadata,
                files=files,
                headers=context.get_auth_headers()
            )
        else:
            result = await client.send_json(
                url=context.callback_url,
                payload=metadata,
                headers=context.get_auth_headers()
            )

        if result.success:
            logger.info(
                f"WebhookSend: Sent {len(files)} files to {context.callback_url}"
            )
        else:
            logger.error(f"WebhookSend failed: {result.error}")

    def _process_images(
        self,
        images: torch.Tensor
    ) -> list[tuple[str, bytes, str]]:
        """Convert image tensor to PNG bytes."""
        results = []

        # Handle batched images
        if len(images.shape) == 4:
            for i in range(images.shape[0]):
                img_tensor = images[i]
                png_bytes = self._tensor_to_png(img_tensor)
                filename = f"webhook_image_{i:05d}.png"
                results.append((filename, png_bytes, "image/png"))
        else:
            png_bytes = self._tensor_to_png(images)
            results.append(("webhook_image_00000.png", png_bytes, "image/png"))

        return results

    def _tensor_to_png(self, tensor: torch.Tensor) -> bytes:
        """Convert single image tensor to PNG bytes."""
        # Tensor is [H, W, C] with values 0-1
        np_image = (tensor.cpu().numpy() * 255).clip(0, 255).astype(np.uint8)
        pil_image = Image.fromarray(np_image)

        buffer = io.BytesIO()
        pil_image.save(buffer, format="PNG", compress_level=4)
        return buffer.getvalue()

    def _process_audio(
        self,
        audio: dict
    ) -> Optional[tuple[str, bytes, str]]:
        """Convert audio dict to FLAC bytes."""
        try:
            import av
        except ImportError:
            logger.warning("av library not available for audio encoding")
            return None

        waveform = audio.get("waveform")
        sample_rate = audio.get("sample_rate", 44100)

        if waveform is None:
            return None

        # Ensure waveform is 2D [channels, samples]
        if len(waveform.shape) == 3:
            waveform = waveform[0]  # Remove batch dimension

        try:
            buffer = io.BytesIO()
            container = av.open(buffer, mode="w", format="flac")

            layout = "mono" if waveform.shape[0] == 1 else "stereo"
            stream = container.add_stream("flac", rate=sample_rate, layout=layout)

            # Convert to numpy
            audio_np = waveform.cpu().numpy()

            # Create audio frame
            frame = av.AudioFrame.from_ndarray(
                audio_np.reshape(1, -1).astype(np.float32),
                format="flt",
                layout=layout,
            )
            frame.sample_rate = sample_rate

            # Encode
            for packet in stream.encode(frame):
                container.mux(packet)
            for packet in stream.encode(None):
                container.mux(packet)

            container.close()
            buffer.seek(0)

            return ("webhook_audio.flac", buffer.getvalue(), "audio/flac")

        except Exception as e:
            logger.error(f"Failed to encode audio: {e}")
            return None


class WebhookSendJSON:
    """
    Send JSON data to webhook endpoint.

    Simpler node for sending just JSON data without file uploads.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "webhook_context": ("WEBHOOK_CONTEXT",),
                "json_data": ("STRING", {
                    "default": "{}",
                    "multiline": True,
                    "tooltip": "JSON data to send"
                }),
            },
            "optional": {
                "event_type": ("STRING", {
                    "default": "custom.data",
                    "tooltip": "Event type for the webhook"
                }),
            },
        }

    RETURN_TYPES = ()
    OUTPUT_NODE = True
    FUNCTION = "send"
    CATEGORY = "webhook"
    DESCRIPTION = "Send JSON data to the webhook endpoint."

    def send(self, webhook_context, json_data, event_type="custom.data"):
        if not isinstance(webhook_context, WebhookContext):
            logger.warning("WebhookSendJSON: Invalid webhook context")
            return {}

        if not webhook_context.callback_url:
            logger.warning("WebhookSendJSON: No callback URL configured")
            return {}

        try:
            # Parse JSON
            try:
                data = json.loads(json_data)
            except json.JSONDecodeError:
                data = {"raw": json_data}

            payload = {
                "event": event_type,
                "request_id": webhook_context.request_id,
                "prompt_id": webhook_context.prompt_id,
                "timestamp": datetime.now().isoformat(),
                "data": data,
            }

            _run_async(self._send_async(webhook_context, payload))
            return {}

        except Exception as e:
            logger.error(f"WebhookSendJSON failed: {e}", exc_info=True)
            return {}

    async def _send_async(self, context: WebhookContext, payload: dict):
        client = get_webhook_client()
        result = await client.send_json(
            url=context.callback_url,
            payload=payload,
            headers=context.get_auth_headers()
        )

        if result.success:
            logger.info(f"WebhookSendJSON: Sent to {context.callback_url}")
        else:
            logger.error(f"WebhookSendJSON failed: {result.error}")
