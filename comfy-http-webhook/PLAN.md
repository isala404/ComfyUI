# ComfyUI HTTP Webhook Node - Implementation Plan

## Executive Summary

This document outlines the design and implementation plan for a production-quality HTTP webhook node system for ComfyUI. The system enables:

1. **Triggering workflows via HTTP** with dynamic variables (text, images, audio, video, embeddings)
2. **Real-time progress updates** sent to external webhook endpoints
3. **Final output delivery via multipart** to callback URLs (ANY output type from any node)
4. **Completion notifications** with status and metadata
5. **Universal output interception** - works with built-in AND custom output nodes

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Input System](#2-input-system)
3. [Output System](#3-output-system)
4. [Node Types](#4-node-types)
5. [Multipart Payload Specifications](#5-multipart-payload-specifications)
6. [HTTP Client Design](#6-http-client-design)
7. [Output Interception (Custom Node Support)](#7-output-interception-custom-node-support)
8. [Error Handling & Reliability](#8-error-handling--reliability)
9. [Edge Cases](#9-edge-cases)
10. [Testing Strategy](#10-testing-strategy)
11. [File Structure](#11-file-structure)
12. [Dependencies](#12-dependencies)

---

## 1. Architecture Overview

### High-Level Design

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           EXTERNAL SYSTEM                                        │
│                                                                                  │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │                         WEBHOOK REQUEST                                   │   │
│  │  POST /prompt                                                            │   │
│  │  {                                                                       │   │
│  │    "prompt": { workflow },                                               │   │
│  │    "extra_data": {                                                       │   │
│  │      "webhook_config": { callback_url, auth, request_id },              │   │
│  │      "webhook_inputs": {                                                 │   │
│  │        "prompt": "a sunset",                                            │   │
│  │        "negative": "blurry",                                            │   │
│  │        "images": ["base64...", "https://..."],  // Multiple images      │   │
│  │        "audio": "base64...",                                            │   │
│  │        "seed": 42                                                       │   │
│  │      }                                                                   │   │
│  │    }                                                                     │   │
│  │  }                                                                       │   │
│  └──────────────────────────────────────────────────────────────────────────┘   │
│                                         │                                        │
│                                         ▼                                        │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │                    WEBHOOK CALLBACK RECEIVER                              │   │
│  │                                                                           │   │
│  │  Receives MULTIPART requests:                                            │   │
│  │  - metadata (JSON part)                                                  │   │
│  │  - file_0 (image/audio/video/mesh binary)                               │   │
│  │  - file_1 ...                                                           │   │
│  └──────────────────────────────────────────────────────────────────────────┘   │
│                                         ▲                                        │
└─────────────────────────────────────────│────────────────────────────────────────┘
                                          │
┌─────────────────────────────────────────│────────────────────────────────────────┐
│                              COMFYUI    │                                         │
│                                         │                                         │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │                           WORKFLOW                                        │   │
│  │                                                                           │   │
│  │   ┌─────────────────┐                                                    │   │
│  │   │ WebhookReceiver │  Extracts config + all input variables             │   │
│  │   │ (Entry Point)   │  from extra_data                                   │   │
│  │   └───────┬─────────┘                                                    │   │
│  │           │                                                               │   │
│  │     ┌─────┴─────┬──────────┬──────────┬──────────┐                       │   │
│  │     ▼           ▼          ▼          ▼          ▼                       │   │
│  │ ┌───────┐  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐                  │   │
│  │ │ Text  │  │ Images │ │ Audio  │ │ Video  │ │ Embed  │                  │   │
│  │ │ Out   │  │ Out    │ │ Out    │ │ Out    │ │ Out    │  Multiple inputs │   │
│  │ └───┬───┘  └───┬────┘ └───┬────┘ └───┬────┘ └───┬────┘  per type        │   │
│  │     │          │          │          │          │                        │   │
│  │     └──────────┴────┬─────┴──────────┴──────────┘                        │   │
│  │                     ▼                                                     │   │
│  │            ┌─────────────────┐                                           │   │
│  │            │ Regular Workflow│  KSampler, VAE, ControlNet, etc.          │   │
│  │            │ Nodes           │                                           │   │
│  │            └────────┬────────┘                                           │   │
│  │                     │                                                     │   │
│  │     ┌───────────────┼───────────────┐                                    │   │
│  │     ▼               ▼               ▼                                    │   │
│  │ ┌────────┐    ┌──────────┐    ┌──────────────┐                          │   │
│  │ │SaveImg │    │SaveAudio │    │ CustomNode   │  ANY output node         │   │
│  │ │(Stock) │    │(Stock)   │    │ OutputXYZ    │  including 3rd party     │   │
│  │ └────┬───┘    └────┬─────┘    └──────┬───────┘                          │   │
│  │      │             │                  │                                   │   │
│  └──────│─────────────│──────────────────│───────────────────────────────────┘   │
│         │             │                  │                                        │
│         ▼             ▼                  ▼                                        │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │                    OUTPUT INTERCEPTOR                                     │   │
│  │                                                                           │   │
│  │  Hooks into ComfyUI execution system to capture ALL outputs:             │   │
│  │  - Intercepts "executed" events from any OUTPUT_NODE                     │   │
│  │  - Detects output type from UI structure (images, audio, 3d, etc.)      │   │
│  │  - Reads saved files from output/temp directories                        │   │
│  │  - Sends via multipart to callback URL                                   │   │
│  └──────────────────────────────────────────────────────────────────────────┘   │
│                                         │                                        │
│                                         ▼                                        │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │                    HTTP CLIENT (Multipart)                                │   │
│  │  - aiohttp.FormData for multipart encoding                               │   │
│  │  - Streaming for large files                                             │   │
│  │  - Exponential backoff with jitter                                       │   │
│  │  - Circuit breaker pattern                                               │   │
│  └──────────────────────────────────────────────────────────────────────────┘   │
│                                                                                  │
└──────────────────────────────────────────────────────────────────────────────────┘
```

### Key Design Principles

1. **Multipart-First**: All outputs sent as multipart/form-data for efficiency
2. **Universal Output Support**: Intercept ANY output node (built-in or custom)
3. **Multi-Input**: Support multiple items of same type (many images, texts)
4. **Non-blocking**: All HTTP calls are async
5. **Reliable**: Retry logic with exponential backoff
6. **Zero-Config for Outputs**: No need to replace output nodes

---

## 2. Input System

### 2.1 Supported Input Types

| Type | Format in webhook_inputs | Output | Notes |
|------|-------------------------|--------|-------|
| **Text** | `"text": "string"` | STRING | Single string |
| **Text Array** | `"texts": ["a", "b"]` | STRING[] | Multiple strings |
| **Integer** | `"seed": 42` | INT | Single integer |
| **Float** | `"cfg": 7.5` | FLOAT | Single float |
| **Boolean** | `"hires": true` | BOOLEAN | True/false |
| **Image (base64)** | `"image": "data:image/png;base64,..."` | IMAGE | Single image tensor |
| **Image (URL)** | `"image": "https://..."` | IMAGE | Downloaded and decoded |
| **Images Array** | `"images": ["base64...", "url..."]` | IMAGE | Batched tensor [N,H,W,C] |
| **Audio (base64)** | `"audio": "data:audio/wav;base64,..."` | AUDIO | Waveform dict |
| **Audio (URL)** | `"audio": "https://..."` | AUDIO | Downloaded and decoded |
| **Video (base64)** | `"video": "data:video/mp4;base64,..."` | VIDEO | Video frames |
| **Video (URL)** | `"video": "https://..."` | VIDEO | Downloaded and decoded |
| **Embedding Name** | `"embedding": "embedding_name"` | STRING | Reference to embedding file |
| **LoRA Name** | `"lora": "lora_name"` | STRING | Reference to LoRA file |
| **Mask (base64)** | `"mask": "data:image/png;base64,..."` | MASK | Grayscale mask tensor |
| **JSON Data** | `"params": {"key": "value"}` | STRING | Serialized JSON |

### 2.2 Input Request Structure

```json
{
  "prompt": { /* ComfyUI workflow JSON */ },
  "extra_data": {
    "webhook_config": {
      "callback_url": "https://api.example.com/webhook",
      "auth_header": "Authorization",
      "auth_value": "Bearer token123",
      "request_id": "req_abc123",
      "send_progress": true,
      "progress_interval_ms": 1000,
      "timeout_seconds": 60,
      "max_retries": 3,
      "include_workflow_in_response": false
    },
    "webhook_inputs": {
      // Text inputs
      "positive_prompt": "a beautiful sunset over mountains, 8k, detailed",
      "negative_prompt": "blurry, low quality",

      // Multiple text inputs (for batch processing)
      "prompts": [
        "a red car",
        "a blue car",
        "a green car"
      ],

      // Numeric inputs
      "seed": 42,
      "cfg_scale": 7.5,
      "steps": 30,
      "width": 1024,
      "height": 1024,

      // Boolean inputs
      "use_hires_fix": true,

      // Single image (base64)
      "init_image": "data:image/png;base64,iVBORw0KGgoAAAANS...",

      // Single image (URL)
      "reference_image": "https://example.com/reference.png",

      // Multiple images (mixed base64 and URLs)
      "control_images": [
        "data:image/png;base64,iVBORw0KGgoAAAANS...",
        "https://example.com/pose.png",
        "data:image/jpeg;base64,/9j/4AAQSkZJRg..."
      ],

      // Mask input
      "inpaint_mask": "data:image/png;base64,iVBORw0KGgoAAAANS...",

      // Audio input
      "audio_input": "data:audio/wav;base64,UklGRiQAAABXQVZF...",

      // Video input
      "video_input": "https://example.com/input_video.mp4",

      // Model references (just names, not files)
      "checkpoint": "sd_xl_base_1.0.safetensors",
      "lora": "detail_enhancer_v1",
      "embedding": "bad_quality_negative",

      // Custom JSON data (passed as string)
      "custom_params": {
        "style": "anime",
        "artist": "studio_ghibli"
      }
    }
  }
}
```

### 2.3 Input Processing Pipeline

```python
class WebhookInputProcessor:
    """Processes all input types from webhook_inputs."""

    async def process_inputs(self, webhook_inputs: dict) -> dict:
        """
        Process all inputs and return ComfyUI-compatible values.

        Returns dict mapping variable_name -> processed_value
        """
        processed = {}

        for key, value in webhook_inputs.items():
            if isinstance(value, str):
                if self._is_base64_image(value):
                    processed[key] = await self._decode_base64_image(value)
                elif self._is_url(value):
                    processed[key] = await self._download_and_decode(value)
                elif self._is_base64_audio(value):
                    processed[key] = await self._decode_base64_audio(value)
                else:
                    processed[key] = value  # Plain string

            elif isinstance(value, list):
                # Handle arrays (multiple images, texts, etc.)
                processed[key] = await self._process_array(value)

            elif isinstance(value, dict):
                # JSON data - serialize to string
                processed[key] = json.dumps(value)

            else:
                # Numbers, booleans - pass through
                processed[key] = value

        return processed

    async def _process_array(self, items: list) -> Union[torch.Tensor, list]:
        """Process array of items, potentially batching images."""
        if not items:
            return []

        # Check if all items are images
        if all(self._is_image_data(item) for item in items):
            tensors = []
            for item in items:
                if self._is_base64_image(item):
                    tensor = await self._decode_base64_image(item)
                elif self._is_url(item):
                    tensor = await self._download_and_decode(item)
                tensors.append(tensor)
            # Stack into batch tensor [N, H, W, C]
            return torch.cat(tensors, dim=0)

        # Otherwise return as list
        return [await self._process_single(item) for item in items]
```

### 2.4 Image Decoding

```python
async def _decode_base64_image(self, data: str) -> torch.Tensor:
    """
    Decode base64 image to tensor.

    Supports:
    - data:image/png;base64,...
    - data:image/jpeg;base64,...
    - data:image/webp;base64,...
    - Raw base64 (no prefix)
    """
    # Strip data URL prefix if present
    if data.startswith("data:"):
        _, data = data.split(",", 1)

    # Decode base64
    image_bytes = base64.b64decode(data)

    # Load with PIL
    pil_image = Image.open(io.BytesIO(image_bytes))
    pil_image = ImageOps.exif_transpose(pil_image)

    # Convert to RGB if needed
    if pil_image.mode != "RGB":
        pil_image = pil_image.convert("RGB")

    # Convert to tensor [1, H, W, C] with values 0-1
    np_image = np.array(pil_image).astype(np.float32) / 255.0
    tensor = torch.from_numpy(np_image).unsqueeze(0)

    return tensor


async def _download_and_decode(self, url: str) -> torch.Tensor:
    """Download image from URL and decode to tensor."""
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=30) as response:
            response.raise_for_status()
            image_bytes = await response.read()

    pil_image = Image.open(io.BytesIO(image_bytes))
    # ... same conversion as above
```

### 2.5 Audio Decoding

```python
async def _decode_base64_audio(self, data: str) -> dict:
    """
    Decode base64 audio to ComfyUI audio format.

    Returns:
        {"waveform": tensor [1, channels, samples], "sample_rate": int}
    """
    if data.startswith("data:"):
        _, data = data.split(",", 1)

    audio_bytes = base64.b64decode(data)

    # Use torchaudio or soundfile
    buffer = io.BytesIO(audio_bytes)
    waveform, sample_rate = torchaudio.load(buffer)

    # Resample to 44100 if needed
    if sample_rate != 44100:
        resampler = torchaudio.transforms.Resample(sample_rate, 44100)
        waveform = resampler(waveform)
        sample_rate = 44100

    return {
        "waveform": waveform.unsqueeze(0),  # [1, channels, samples]
        "sample_rate": sample_rate
    }
```

---

## 3. Output System

### 3.1 Multipart Output Format

**ALL outputs are sent as multipart/form-data** with the following structure:

```
Content-Type: multipart/form-data; boundary=----WebhookBoundary

------WebhookBoundary
Content-Disposition: form-data; name="metadata"
Content-Type: application/json

{
  "event": "output.batch",
  "request_id": "req_abc123",
  "prompt_id": "comfy_12345",
  "timestamp": "2024-01-15T10:30:00.000Z",
  "version": "1.0",
  "outputs": [
    {
      "index": 0,
      "type": "image",
      "format": "png",
      "filename": "ComfyUI_00001_.png",
      "width": 1024,
      "height": 1024,
      "node_id": "9",
      "node_type": "SaveImage"
    },
    {
      "index": 1,
      "type": "image",
      "format": "png",
      "filename": "ComfyUI_00002_.png",
      "width": 1024,
      "height": 1024,
      "node_id": "9",
      "node_type": "SaveImage"
    },
    {
      "index": 2,
      "type": "audio",
      "format": "flac",
      "filename": "audio_00001_.flac",
      "sample_rate": 44100,
      "duration_seconds": 5.2,
      "node_id": "15",
      "node_type": "SaveAudio"
    }
  ],
  "execution_time_ms": 12345,
  "custom_metadata": { ... }
}
------WebhookBoundary
Content-Disposition: form-data; name="file_0"; filename="ComfyUI_00001_.png"
Content-Type: image/png

<binary PNG data>
------WebhookBoundary
Content-Disposition: form-data; name="file_1"; filename="ComfyUI_00002_.png"
Content-Type: image/png

<binary PNG data>
------WebhookBoundary
Content-Disposition: form-data; name="file_2"; filename="audio_00001_.flac"
Content-Type: audio/flac

<binary FLAC data>
------WebhookBoundary--
```

### 3.2 Supported Output Types

| UI Key | Output Type | MIME Type | File Extensions |
|--------|-------------|-----------|-----------------|
| `images` | Image | image/png, image/jpeg, image/webp | .png, .jpg, .webp |
| `audio` | Audio | audio/flac, audio/mpeg, audio/ogg | .flac, .mp3, .opus |
| `video` | Video | video/webm, video/mp4 | .webm, .mp4 |
| `3d` | 3D Mesh | model/gltf-binary, text/plain | .glb, .obj |
| `latents` | Latent | application/octet-stream | .latent |
| `text` | Text | text/plain | - |
| `result` | 3D Preview | application/json | - |
| Custom | Generic | application/octet-stream | varies |

### 3.3 Output Detection from UI Structure

```python
def detect_output_type(ui_output: dict) -> list[OutputInfo]:
    """
    Detect output type from ComfyUI UI return structure.

    Known UI structures:
    - {"images": [{filename, subfolder, type}, ...]}
    - {"audio": [{filename, subfolder, type}, ...]}
    - {"3d": [{filename, subfolder, type}, ...]}
    - {"latents": [{filename, subfolder, type}, ...]}
    - {"text": (value,)}
    - {"result": [model_file, camera_info, bg_image]}
    """
    outputs = []

    if "images" in ui_output:
        for item in ui_output["images"]:
            outputs.append(OutputInfo(
                type="image",
                filename=item["filename"],
                subfolder=item.get("subfolder", ""),
                folder_type=item.get("type", "output"),
                mime_type=guess_mime_type(item["filename"]),
            ))

    elif "audio" in ui_output:
        for item in ui_output["audio"]:
            outputs.append(OutputInfo(
                type="audio",
                filename=item["filename"],
                subfolder=item.get("subfolder", ""),
                folder_type=item.get("type", "output"),
                mime_type=guess_mime_type(item["filename"]),
            ))

    elif "3d" in ui_output:
        for item in ui_output["3d"]:
            outputs.append(OutputInfo(
                type="mesh",
                filename=item["filename"],
                subfolder=item.get("subfolder", ""),
                folder_type=item.get("type", "output"),
                mime_type="model/gltf-binary",
            ))

    elif "latents" in ui_output:
        for item in ui_output["latents"]:
            outputs.append(OutputInfo(
                type="latent",
                filename=item["filename"],
                subfolder=item.get("subfolder", ""),
                folder_type=item.get("type", "output"),
                mime_type="application/octet-stream",
            ))

    elif "text" in ui_output:
        # Text outputs are inline, not files
        text_value = ui_output["text"][0] if ui_output["text"] else ""
        outputs.append(OutputInfo(
            type="text",
            inline_content=text_value,
            mime_type="text/plain",
        ))

    elif "result" in ui_output:
        # 3D preview - complex structure
        outputs.append(OutputInfo(
            type="3d_preview",
            inline_content=json.dumps(ui_output["result"]),
            mime_type="application/json",
        ))

    else:
        # Unknown structure - try to extract any file references
        for key, value in ui_output.items():
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, dict) and "filename" in item:
                        outputs.append(OutputInfo(
                            type="unknown",
                            filename=item["filename"],
                            subfolder=item.get("subfolder", ""),
                            folder_type=item.get("type", "output"),
                            mime_type="application/octet-stream",
                        ))

    return outputs
```

---

## 4. Node Types

### 4.1 WebhookReceiver Node (Entry Point)

**Purpose**: Single entry point that extracts config and all inputs from extra_data.

```python
class WebhookReceiver:
    """
    Entry point for webhook-triggered workflows.
    Extracts configuration and all input variables from extra_data.
    """

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {},
            "optional": {
                # Defaults used if not provided in webhook_config
                "default_callback_url": ("STRING", {"default": ""}),
                "default_timeout": ("INT", {"default": 30, "min": 1, "max": 300}),
                "default_max_retries": ("INT", {"default": 3, "min": 0, "max": 10}),
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

    def receive(self, prompt=None, extra_pnginfo=None, unique_id=None, **kwargs):
        # Extract webhook_config from extra_data
        extra_data = extra_pnginfo or {}
        webhook_config = extra_data.get("webhook_config", {})
        webhook_inputs = extra_data.get("webhook_inputs", {})

        context = WebhookContext(
            callback_url=webhook_config.get("callback_url", kwargs.get("default_callback_url")),
            request_id=webhook_config.get("request_id", str(uuid.uuid4())),
            auth_header=webhook_config.get("auth_header"),
            auth_value=webhook_config.get("auth_value"),
            send_progress=webhook_config.get("send_progress", True),
            timeout=webhook_config.get("timeout_seconds", kwargs.get("default_timeout", 30)),
            max_retries=webhook_config.get("max_retries", kwargs.get("default_max_retries", 3)),
            inputs=webhook_inputs,
            prompt_id=unique_id,
        )

        # Register this context for output interception
        register_webhook_context(context)

        return (context,)
```

### 4.2 WebhookInput Nodes (Extract Specific Inputs)

```python
class WebhookTextInput:
    """Extract text input from webhook context."""

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "webhook_context": ("WEBHOOK_CONTEXT",),
                "input_name": ("STRING", {"default": "prompt"}),
                "default_value": ("STRING", {"default": "", "multiline": True}),
            },
        }

    RETURN_TYPES = ("STRING",)
    FUNCTION = "extract"
    CATEGORY = "webhook/inputs"

    def extract(self, webhook_context, input_name, default_value):
        value = webhook_context.inputs.get(input_name, default_value)
        return (str(value),)


class WebhookTextsInput:
    """Extract multiple text inputs as a list."""

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "webhook_context": ("WEBHOOK_CONTEXT",),
                "input_name": ("STRING", {"default": "prompts"}),
            },
        }

    RETURN_TYPES = ("STRING",)
    OUTPUT_IS_LIST = (True,)  # Output is a list
    FUNCTION = "extract"
    CATEGORY = "webhook/inputs"

    def extract(self, webhook_context, input_name):
        values = webhook_context.inputs.get(input_name, [])
        if isinstance(values, str):
            values = [values]
        return (values,)


class WebhookImageInput:
    """Extract single image from webhook context."""

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "webhook_context": ("WEBHOOK_CONTEXT",),
                "input_name": ("STRING", {"default": "image"}),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "extract"
    CATEGORY = "webhook/inputs"

    async def extract(self, webhook_context, input_name):
        value = webhook_context.inputs.get(input_name)
        if value is None:
            # Return empty image
            return (torch.zeros(1, 64, 64, 3),)

        processor = WebhookInputProcessor()
        tensor = await processor.process_image(value)
        return (tensor,)


class WebhookImagesInput:
    """Extract multiple images as batched tensor."""

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "webhook_context": ("WEBHOOK_CONTEXT",),
                "input_name": ("STRING", {"default": "images"}),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "extract"
    CATEGORY = "webhook/inputs"

    async def extract(self, webhook_context, input_name):
        values = webhook_context.inputs.get(input_name, [])
        if not values:
            return (torch.zeros(1, 64, 64, 3),)

        if not isinstance(values, list):
            values = [values]

        processor = WebhookInputProcessor()
        tensors = []
        for value in values:
            tensor = await processor.process_image(value)
            tensors.append(tensor)

        # Batch all images [N, H, W, C]
        # Note: Images may need resizing to match
        batched = torch.cat(tensors, dim=0)
        return (batched,)


class WebhookAudioInput:
    """Extract audio from webhook context."""

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "webhook_context": ("WEBHOOK_CONTEXT",),
                "input_name": ("STRING", {"default": "audio"}),
            },
        }

    RETURN_TYPES = ("AUDIO",)
    FUNCTION = "extract"
    CATEGORY = "webhook/inputs"

    async def extract(self, webhook_context, input_name):
        value = webhook_context.inputs.get(input_name)
        if value is None:
            return ({"waveform": torch.zeros(1, 1, 44100), "sample_rate": 44100},)

        processor = WebhookInputProcessor()
        audio = await processor.process_audio(value)
        return (audio,)


class WebhookIntInput:
    """Extract integer from webhook context."""

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "webhook_context": ("WEBHOOK_CONTEXT",),
                "input_name": ("STRING", {"default": "seed"}),
                "default_value": ("INT", {"default": 0}),
            },
        }

    RETURN_TYPES = ("INT",)
    FUNCTION = "extract"
    CATEGORY = "webhook/inputs"

    def extract(self, webhook_context, input_name, default_value):
        value = webhook_context.inputs.get(input_name, default_value)
        return (int(value),)


class WebhookFloatInput:
    """Extract float from webhook context."""

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "webhook_context": ("WEBHOOK_CONTEXT",),
                "input_name": ("STRING", {"default": "cfg"}),
                "default_value": ("FLOAT", {"default": 7.0}),
            },
        }

    RETURN_TYPES = ("FLOAT",)
    FUNCTION = "extract"
    CATEGORY = "webhook/inputs"

    def extract(self, webhook_context, input_name, default_value):
        value = webhook_context.inputs.get(input_name, default_value)
        return (float(value),)


class WebhookBoolInput:
    """Extract boolean from webhook context."""

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "webhook_context": ("WEBHOOK_CONTEXT",),
                "input_name": ("STRING", {"default": "use_hires"}),
                "default_value": ("BOOLEAN", {"default": False}),
            },
        }

    RETURN_TYPES = ("BOOLEAN",)
    FUNCTION = "extract"
    CATEGORY = "webhook/inputs"

    def extract(self, webhook_context, input_name, default_value):
        value = webhook_context.inputs.get(input_name, default_value)
        return (bool(value),)


class WebhookMaskInput:
    """Extract mask from webhook context."""

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "webhook_context": ("WEBHOOK_CONTEXT",),
                "input_name": ("STRING", {"default": "mask"}),
            },
        }

    RETURN_TYPES = ("MASK",)
    FUNCTION = "extract"
    CATEGORY = "webhook/inputs"

    async def extract(self, webhook_context, input_name):
        value = webhook_context.inputs.get(input_name)
        if value is None:
            return (torch.zeros(1, 64, 64),)

        processor = WebhookInputProcessor()
        mask = await processor.process_mask(value)
        return (mask,)


class WebhookVideoInput:
    """Extract video from webhook context."""

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "webhook_context": ("WEBHOOK_CONTEXT",),
                "input_name": ("STRING", {"default": "video"}),
            },
        }

    RETURN_TYPES = ("VIDEO",)
    FUNCTION = "extract"
    CATEGORY = "webhook/inputs"

    async def extract(self, webhook_context, input_name):
        value = webhook_context.inputs.get(input_name)
        if value is None:
            return (None,)

        processor = WebhookInputProcessor()
        video = await processor.process_video(value)
        return (video,)


class WebhookJSONInput:
    """Extract JSON data as string from webhook context."""

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "webhook_context": ("WEBHOOK_CONTEXT",),
                "input_name": ("STRING", {"default": "params"}),
            },
        }

    RETURN_TYPES = ("STRING",)
    FUNCTION = "extract"
    CATEGORY = "webhook/inputs"

    def extract(self, webhook_context, input_name):
        value = webhook_context.inputs.get(input_name, {})
        if isinstance(value, dict):
            return (json.dumps(value),)
        return (str(value),)
```

### 4.3 WebhookSend Node (Manual Output Send)

```python
class WebhookSend:
    """
    Manually send data to webhook.
    Use this when you need to send outputs that aren't from standard output nodes.
    """

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "webhook_context": ("WEBHOOK_CONTEXT",),
            },
            "optional": {
                "images": ("IMAGE",),
                "audio": ("AUDIO",),
                "video": ("VIDEO",),
                "text": ("STRING", {"multiline": True}),
                "data": ("*",),  # Any type
            },
        }

    RETURN_TYPES = ()
    OUTPUT_NODE = True
    FUNCTION = "send"
    CATEGORY = "webhook"

    async def send(self, webhook_context, images=None, audio=None, video=None, text=None, data=None):
        client = get_webhook_client()
        outputs = []

        if images is not None:
            outputs.extend(process_image_outputs(images))

        if audio is not None:
            outputs.extend(process_audio_outputs(audio))

        if video is not None:
            outputs.extend(process_video_outputs(video))

        if text is not None:
            outputs.append(OutputInfo(type="text", inline_content=text))

        if data is not None:
            outputs.append(process_generic_output(data))

        await client.send_multipart_outputs(
            url=webhook_context.callback_url,
            outputs=outputs,
            context=webhook_context,
        )

        return {}
```

---

## 5. Multipart Payload Specifications

### 5.1 Event Types

| Event | When Sent | Contains Files |
|-------|-----------|----------------|
| `workflow.started` | Execution begins | No |
| `workflow.progress` | During node execution | No |
| `output.ready` | Single output node completes | Yes |
| `output.batch` | All outputs complete (final) | Yes |
| `workflow.completed` | Execution succeeds | Optional |
| `workflow.error` | Execution fails | No |
| `workflow.interrupted` | User cancels | No |

### 5.2 Progress Event (JSON only)

```json
POST /webhook
Content-Type: application/json

{
  "event": "workflow.progress",
  "request_id": "req_abc123",
  "prompt_id": "comfy_12345",
  "timestamp": "2024-01-15T10:30:00.000Z",
  "node_id": "7",
  "node_type": "KSampler",
  "progress": 0.45,
  "message": "Sampling step 9/20",
  "elapsed_ms": 5234
}
```

### 5.3 Output Ready Event (Multipart)

Sent when individual output node completes (streaming mode):

```
POST /webhook
Content-Type: multipart/form-data; boundary=----WebhookBoundary

------WebhookBoundary
Content-Disposition: form-data; name="metadata"
Content-Type: application/json

{
  "event": "output.ready",
  "request_id": "req_abc123",
  "prompt_id": "comfy_12345",
  "timestamp": "2024-01-15T10:30:05.000Z",
  "output": {
    "index": 0,
    "type": "image",
    "format": "png",
    "filename": "ComfyUI_00001_.png",
    "width": 1024,
    "height": 1024,
    "node_id": "9",
    "node_type": "SaveImage",
    "seed": 42
  }
}
------WebhookBoundary
Content-Disposition: form-data; name="file"; filename="ComfyUI_00001_.png"
Content-Type: image/png

<binary PNG data>
------WebhookBoundary--
```

### 5.4 Batch Output Event (Multipart - Final)

Sent after all outputs complete:

```
POST /webhook
Content-Type: multipart/form-data; boundary=----WebhookBoundary

------WebhookBoundary
Content-Disposition: form-data; name="metadata"
Content-Type: application/json

{
  "event": "output.batch",
  "request_id": "req_abc123",
  "prompt_id": "comfy_12345",
  "timestamp": "2024-01-15T10:30:10.000Z",
  "status": "success",
  "outputs": [
    {
      "index": 0,
      "type": "image",
      "format": "png",
      "filename": "ComfyUI_00001_.png",
      "width": 1024,
      "height": 1024,
      "file_size_bytes": 1234567,
      "node_id": "9",
      "node_type": "SaveImage"
    },
    {
      "index": 1,
      "type": "audio",
      "format": "flac",
      "filename": "audio_00001_.flac",
      "sample_rate": 44100,
      "duration_seconds": 5.2,
      "file_size_bytes": 567890,
      "node_id": "15",
      "node_type": "SaveAudio"
    }
  ],
  "execution_time_ms": 12345,
  "nodes_executed": 15,
  "custom_metadata": {}
}
------WebhookBoundary
Content-Disposition: form-data; name="file_0"; filename="ComfyUI_00001_.png"
Content-Type: image/png

<binary PNG data>
------WebhookBoundary
Content-Disposition: form-data; name="file_1"; filename="audio_00001_.flac"
Content-Type: audio/flac

<binary FLAC data>
------WebhookBoundary--
```

### 5.5 Error Event (JSON only)

```json
POST /webhook
Content-Type: application/json

{
  "event": "workflow.error",
  "request_id": "req_abc123",
  "prompt_id": "comfy_12345",
  "timestamp": "2024-01-15T10:30:00.000Z",
  "error": {
    "type": "execution_error",
    "message": "CUDA out of memory",
    "node_id": "7",
    "node_type": "KSampler",
    "traceback": "Traceback (most recent call last):\n..."
  },
  "partial_outputs": [
    {
      "index": 0,
      "type": "image",
      "filename": "ComfyUI_00001_.png"
    }
  ]
}
```

---

## 6. HTTP Client Design

### 6.1 Multipart Client

```python
class WebhookClient:
    """
    Production-grade async HTTP client for multipart webhook delivery.
    """

    def __init__(
        self,
        timeout: float = 60.0,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        jitter_factor: float = 0.2,
    ):
        self._session: Optional[aiohttp.ClientSession] = None
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.jitter_factor = jitter_factor

    async def get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session with connection pooling."""
        if self._session is None or self._session.closed:
            connector = aiohttp.TCPConnector(
                limit=10,  # Max connections
                limit_per_host=5,
                keepalive_timeout=30,
            )
            self._session = aiohttp.ClientSession(
                connector=connector,
                timeout=self.timeout,
            )
        return self._session

    async def send_json(
        self,
        url: str,
        payload: dict,
        headers: Optional[dict] = None,
    ) -> WebhookResult:
        """Send JSON payload (for progress, errors)."""
        session = await self.get_session()
        all_headers = {"Content-Type": "application/json"}
        if headers:
            all_headers.update(headers)

        return await self._execute_with_retry(
            lambda: session.post(url, json=payload, headers=all_headers)
        )

    async def send_multipart(
        self,
        url: str,
        metadata: dict,
        files: list[tuple[str, str, bytes, str]],  # (name, filename, data, content_type)
        headers: Optional[dict] = None,
    ) -> WebhookResult:
        """
        Send multipart request with files.

        Args:
            url: Webhook URL
            metadata: JSON metadata dict
            files: List of (field_name, filename, binary_data, mime_type)
            headers: Optional auth headers
        """
        session = await self.get_session()

        # Build FormData
        form = aiohttp.FormData()

        # Add metadata as JSON part
        form.add_field(
            "metadata",
            json.dumps(metadata),
            content_type="application/json",
        )

        # Add files
        for name, filename, data, content_type in files:
            form.add_field(
                name,
                data,
                filename=filename,
                content_type=content_type,
            )

        return await self._execute_with_retry(
            lambda: session.post(url, data=form, headers=headers)
        )

    async def send_multipart_streaming(
        self,
        url: str,
        metadata: dict,
        file_paths: list[tuple[str, str, str, str]],  # (name, filename, path, content_type)
        headers: Optional[dict] = None,
    ) -> WebhookResult:
        """
        Send multipart with files streamed from disk (for large files).
        """
        session = await self.get_session()

        # Use MultipartWriter for streaming
        with aiohttp.MultipartWriter("form-data") as mpwriter:
            # Add metadata
            metadata_payload = aiohttp.payload.JsonPayload(metadata)
            metadata_payload.set_content_disposition("form-data", name="metadata")
            mpwriter.append_payload(metadata_payload)

            # Add files (streamed)
            for name, filename, path, content_type in file_paths:
                file_payload = aiohttp.payload.FilePayload(
                    path,
                    filename=filename,
                    content_type=content_type,
                )
                file_payload.set_content_disposition("form-data", name=name, filename=filename)
                mpwriter.append_payload(file_payload)

            return await self._execute_with_retry(
                lambda: session.post(url, data=mpwriter, headers=headers)
            )

    async def _execute_with_retry(self, request_func) -> WebhookResult:
        """Execute request with exponential backoff and jitter."""
        last_error = None

        for attempt in range(self.max_retries + 1):
            try:
                if attempt > 0:
                    delay = self._calculate_delay(attempt)
                    logging.info(f"Webhook retry {attempt}/{self.max_retries} after {delay:.2f}s")
                    await asyncio.sleep(delay)

                async with request_func() as response:
                    if response.status < 400:
                        return WebhookResult(success=True, status=response.status)

                    # Check if retryable
                    if response.status in (408, 429, 500, 502, 503, 504):
                        last_error = f"HTTP {response.status}"
                        continue

                    # Non-retryable error
                    body = await response.text()
                    return WebhookResult(
                        success=False,
                        status=response.status,
                        error=f"HTTP {response.status}: {body[:200]}",
                    )

            except aiohttp.ClientError as e:
                last_error = str(e)
                continue
            except asyncio.TimeoutError:
                last_error = "Request timeout"
                continue

        return WebhookResult(success=False, error=last_error)

    def _calculate_delay(self, attempt: int) -> float:
        """Exponential backoff with jitter."""
        delay = min(self.base_delay * (2 ** (attempt - 1)), self.max_delay)
        jitter = delay * self.jitter_factor * (random.random() * 2 - 1)
        return max(0.1, delay + jitter)

    async def close(self):
        """Close the session."""
        if self._session and not self._session.closed:
            await self._session.close()
```

---

## 7. Output Interception (Custom Node Support)

### 7.1 Interception Strategy

To support ANY output node (including custom/3rd party nodes) without requiring users to modify their workflows:

**Strategy: Hook into `task_done` in PromptQueue**

```python
# In __init__.py of the extension

import execution

_original_task_done = None

def install_output_interceptor():
    """Install hook to intercept all workflow outputs."""
    global _original_task_done

    # Store original
    _original_task_done = execution.PromptQueue.task_done

    # Replace with our interceptor
    execution.PromptQueue.task_done = _intercepted_task_done

def _intercepted_task_done(self, item_id, history_result, status, process_item=None):
    """Intercept task completion to capture all outputs."""

    # Get prompt info
    prompt = self.currently_running.get(item_id)
    if prompt:
        prompt_id = prompt[1]
        extra_data = prompt[3] if len(prompt) > 3 else {}

        # Check if this workflow has webhook config
        webhook_config = extra_data.get("webhook_config")
        if webhook_config:
            # Extract outputs from history_result
            outputs = history_result.get("outputs", {})

            # Process and send outputs
            asyncio.create_task(
                _send_webhook_outputs(webhook_config, prompt_id, outputs, status)
            )

    # Call original
    return _original_task_done(self, item_id, history_result, status, process_item)


async def _send_webhook_outputs(webhook_config, prompt_id, outputs, status):
    """Send all outputs to webhook."""
    client = get_webhook_client()

    all_files = []
    all_metadata = []

    # Process each output node's results
    for node_id, node_output in outputs.items():
        output_infos = detect_output_type(node_output)

        for info in output_infos:
            if info.filename:
                # Read file from disk
                file_path = get_output_path(info.filename, info.subfolder, info.folder_type)
                if os.path.exists(file_path):
                    with open(file_path, "rb") as f:
                        file_data = f.read()

                    all_files.append((
                        f"file_{len(all_files)}",
                        info.filename,
                        file_data,
                        info.mime_type,
                    ))
                    all_metadata.append(info.to_dict())

            elif info.inline_content:
                # Inline content (text, etc.)
                all_metadata.append(info.to_dict())

    # Build metadata payload
    metadata = {
        "event": "output.batch",
        "request_id": webhook_config.get("request_id", str(uuid.uuid4())),
        "prompt_id": prompt_id,
        "timestamp": datetime.now().isoformat(),
        "status": status.status_str if status else "unknown",
        "outputs": all_metadata,
    }

    # Send multipart
    await client.send_multipart(
        url=webhook_config["callback_url"],
        metadata=metadata,
        files=all_files,
        headers=_get_auth_headers(webhook_config),
    )
```

### 7.2 Alternative: Progress Handler Hook

For real-time output streaming (send each output as it completes):

```python
class WebhookProgressHandler(ProgressHandler):
    """Custom progress handler that sends outputs to webhook."""

    def __init__(self, webhook_config):
        super().__init__("webhook")
        self.webhook_config = webhook_config
        self.client = get_webhook_client()

    def finish_handler(self, node_id, entry, prompt_id):
        """Called when a node finishes - check for outputs."""
        # Get the node's output from cache
        cached = get_cached_output(node_id)
        if cached and cached.ui:
            # This node produced UI output - send it
            asyncio.create_task(
                self._send_node_output(node_id, cached.ui, prompt_id)
            )

    async def _send_node_output(self, node_id, ui_output, prompt_id):
        """Send individual node output to webhook."""
        output_infos = detect_output_type(ui_output)
        # ... send multipart ...
```

### 7.3 Supported Custom Node Output Patterns

The interceptor handles ANY of these UI return patterns from custom nodes:

```python
# Pattern 1: Standard file outputs
return {"ui": {"images": [{"filename": "...", "subfolder": "...", "type": "output"}]}}
return {"ui": {"audio": [{"filename": "...", "subfolder": "...", "type": "output"}]}}

# Pattern 2: Text outputs
return {"ui": {"text": ("some text value",)}}

# Pattern 3: Custom key with file list
return {"ui": {"my_custom_output": [{"filename": "...", ...}]}}

# Pattern 4: Nested structures
return {"ui": {"result": [model_file, camera_info, bg_image]}}

# Pattern 5: Mixed outputs
return {"ui": {"images": [...], "text": ("caption",)}}

# Pattern 6: NodeOutput (V3 API)
return io.NodeOutput(ui=ui.PreviewImage(tensor))
return io.NodeOutput(ui={"custom": data})
```

---

## 8. Error Handling & Reliability

### 8.1 Error Categories

| Category | Handling | Retry | Example |
|----------|----------|-------|---------|
| Network Errors | Retry with backoff | Yes | Connection refused |
| Server 5xx | Retry with backoff | Yes | 500, 502, 503 |
| Rate Limited | Retry with longer delay | Yes | 429 |
| Client 4xx | No retry, log | No | 400, 401, 403 |
| Timeout | Retry with backoff | Yes | Request timeout |
| File Not Found | Log warning, skip | No | Output file missing |

### 8.2 Graceful Degradation

```python
async def send_with_fallback(self, context, outputs):
    """Send outputs with fallback strategies."""
    try:
        # Try multipart first
        result = await self.client.send_multipart(...)
        if result.success:
            return result

    except Exception as e:
        logging.error(f"Multipart send failed: {e}")

    # Fallback 1: Try sending files individually
    for output in outputs:
        try:
            await self.client.send_single_output(...)
        except Exception as e:
            logging.error(f"Individual send failed for {output.filename}: {e}")

    # Fallback 2: Queue for later retry
    await self.queue_for_retry(context, outputs)

    # Always save locally regardless of webhook success
    return WebhookResult(success=False, error="All send methods failed")
```

---

## 9. Edge Cases

### 9.1 Multiple Images with Different Sizes

**Problem**: Batching images of different sizes into tensor.

**Solution**: Resize to largest or pad.

```python
def batch_images_mixed_sizes(tensors: list[torch.Tensor]) -> torch.Tensor:
    """Batch images that may have different sizes."""
    if not tensors:
        return torch.zeros(0, 64, 64, 3)

    # Find max dimensions
    max_h = max(t.shape[1] for t in tensors)
    max_w = max(t.shape[2] for t in tensors)

    # Pad all images to max size
    padded = []
    for t in tensors:
        h, w = t.shape[1], t.shape[2]
        if h < max_h or w < max_w:
            # Center pad
            pad_h = (max_h - h) // 2
            pad_w = (max_w - w) // 2
            t = F.pad(t, (0, 0, pad_w, max_w - w - pad_w, pad_h, max_h - h - pad_h))
        padded.append(t)

    return torch.cat(padded, dim=0)
```

### 9.2 Very Large Files

**Problem**: Files too large for single HTTP request.

**Solution**: Stream from disk, chunked encoding.

```python
# Use streaming multipart for files > 50MB
STREAM_THRESHOLD = 50 * 1024 * 1024

async def send_outputs(self, outputs):
    large_files = [o for o in outputs if o.file_size > STREAM_THRESHOLD]

    if large_files:
        # Stream from disk
        await self.client.send_multipart_streaming(...)
    else:
        # Load into memory
        await self.client.send_multipart(...)
```

### 9.3 Concurrent Webhooks

**Problem**: Multiple workflows sending to same endpoint.

**Solution**: Isolated contexts, request IDs.

### 9.4 Custom Node Unknown Output Format

**Problem**: Custom node returns unexpected UI structure.

**Solution**: Generic fallback with logging.

```python
def detect_output_type(ui_output):
    # ... try known patterns ...

    # Fallback: serialize entire structure as JSON
    logging.warning(f"Unknown output format, serializing as JSON: {list(ui_output.keys())}")
    return [OutputInfo(
        type="unknown",
        inline_content=json.dumps(ui_output),
        mime_type="application/json",
    )]
```

---

## 10. Testing Strategy

### 10.1 Input Processing Tests

```python
class TestInputProcessing:
    async def test_base64_image_decode(self):
        """Test base64 image decoding."""

    async def test_url_image_download(self):
        """Test URL image download and decode."""

    async def test_multiple_images_batch(self):
        """Test batching multiple images into tensor."""

    async def test_audio_decode(self):
        """Test audio decoding from base64."""

    async def test_mixed_input_types(self):
        """Test processing mixed input types."""
```

### 10.2 Output Detection Tests

```python
class TestOutputDetection:
    def test_detect_image_output(self):
        """Test detection of image outputs."""

    def test_detect_audio_output(self):
        """Test detection of audio outputs."""

    def test_detect_custom_output(self):
        """Test detection of custom node outputs."""

    def test_detect_unknown_fallback(self):
        """Test fallback for unknown output types."""
```

### 10.3 Multipart Tests

```python
class TestMultipartClient:
    async def test_multipart_single_file(self):
        """Test multipart with single file."""

    async def test_multipart_multiple_files(self):
        """Test multipart with multiple files."""

    async def test_multipart_streaming(self):
        """Test streaming multipart for large files."""

    async def test_retry_on_failure(self):
        """Test retry behavior."""
```

---

## 11. File Structure

```
comfy-http-webhook/
├── __init__.py                  # Node registration + interceptor install
├── PLAN.md                      # This document
├── TODOs.md                     # Implementation checklist
├── README.md                    # User documentation
├── requirements.txt             # Dependencies
│
├── nodes/
│   ├── __init__.py
│   ├── receiver.py              # WebhookReceiver node
│   ├── inputs.py                # All WebhookInput nodes
│   └── send.py                  # WebhookSend manual output node
│
├── core/
│   ├── __init__.py
│   ├── client.py                # WebhookClient (multipart)
│   ├── context.py               # WebhookContext management
│   ├── interceptor.py           # Output interception hooks
│   └── types.py                 # Data types
│
├── processors/
│   ├── __init__.py
│   ├── inputs.py                # Input processing (images, audio, etc.)
│   ├── outputs.py               # Output detection and processing
│   └── mime.py                  # MIME type utilities
│
├── utils/
│   ├── __init__.py
│   ├── validation.py            # URL/input validation
│   └── logging.py               # Logging utilities
│
└── tests/
    ├── __init__.py
    ├── test_inputs.py
    ├── test_outputs.py
    ├── test_client.py
    ├── test_interceptor.py
    ├── test_e2e.py
    └── mock_server.py
```

---

## 12. Dependencies

### Required

```
aiohttp>=3.8.0          # Async HTTP client with multipart
```

### Optional

```
torchaudio>=2.0.0       # Audio processing (usually in ComfyUI)
av>=10.0.0              # Video processing (usually in ComfyUI)
```

### Development

```
pytest>=7.0.0
pytest-asyncio>=0.21.0
aioresponses>=0.7.0     # Mock aiohttp
```

---

## References

- [aiohttp Multipart Documentation](https://docs.aiohttp.org/en/stable/multipart.html)
- [aiohttp FormData](https://docs.aiohttp.org/en/stable/client_quickstart.html#post-a-multipart-encoded-file)
- [ComfyUI Execution System](https://docs.comfy.org/development/comfyui-server)
- [SaladTechnologies/comfyui-api](https://github.com/SaladTechnologies/comfyui-api)
