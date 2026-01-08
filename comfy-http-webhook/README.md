# ComfyUI HTTP Webhook Node

A production-quality custom node package for ComfyUI that enables HTTP webhook integration for triggering workflows and receiving outputs.

## Features

- **🚀 Zero-Config Mode** - Just add `webhook_config` to your API request, no workflow changes needed!
- **Trigger workflows via HTTP** with dynamic variables (text, images, audio, video, masks)
- **Real-time progress updates** sent to your webhook endpoint
- **Multipart output delivery** for images, audio, video, and 3D meshes
- **Universal output interception** - works with built-in AND custom output nodes
- **Reliable delivery** with exponential backoff retry logic
- **Production-ready** with error handling, logging, and authentication support

## Installation

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/your-repo/comfy-http-webhook.git
pip install -r comfy-http-webhook/requirements.txt
```

## Quick Start

### Option 1: Zero-Config Mode (Easiest!) ⭐

**No workflow changes needed!** Just add `webhook_config` to any existing workflow:

```json
POST /prompt
{
  "prompt": { /* your existing workflow JSON - no changes needed */ },
  "extra_data": {
    "webhook_config": {
      "callback_url": "https://your-server.com/webhook",
      "auth_header": "Authorization",
      "auth_value": "Bearer your-token"
    }
  }
}
```

That's it! When the workflow completes, all outputs (images, audio, video, etc.) are automatically sent to your webhook URL as a multipart request.

**How it works:**
1. The webhook interceptor hooks into ComfyUI's execution system
2. When any workflow with `webhook_config` completes, outputs are captured
3. All output files are sent via multipart POST to your `callback_url`
4. Works with SaveImage, SaveAudio, Preview nodes, custom nodes - everything!

### Option 2: With Dynamic Inputs

For workflows that need dynamic inputs (prompts, seeds, images from API):

**1. Add WebhookReceiver node to your workflow**

The `WebhookReceiver` node extracts configuration and input variables from the API request.

**2. Connect WebhookInput nodes for each dynamic value:**

- `WebhookTextInput` - Extract text strings (prompts)
- `WebhookIntInput` - Extract integers (seeds, steps)
- `WebhookFloatInput` - Extract floats (cfg, denoise)
- `WebhookImageInput` - Extract images (base64 or URL)
- `WebhookAudioInput` - Extract audio
- And more...

**3. Submit via API with inputs:**

```json
POST /prompt
{
  "prompt": { /* workflow with WebhookReceiver and WebhookInput nodes */ },
  "extra_data": {
    "webhook_config": {
      "callback_url": "https://your-server.com/webhook"
    },
    "webhook_inputs": {
      "prompt": "a beautiful sunset over mountains, 8k",
      "negative": "blurry, low quality",
      "seed": 42,
      "cfg": 7.5,
      "image": "data:image/png;base64,iVBORw0KGgo..."
    }
  }
}
```

## API Reference

### webhook_config Options

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `callback_url` | string | required | URL to receive webhook events |
| `request_id` | string | auto-generated | Unique identifier for this request |
| `auth_header` | string | null | Header name for authentication |
| `auth_value` | string | null | Header value for authentication |
| `headers` | object | null | Additional custom headers |
| `send_progress` | boolean | true | Send progress events during execution |
| `timeout_seconds` | integer | 60 | Request timeout for webhook calls |
| `max_retries` | integer | 3 | Maximum retry attempts on failure |

### webhook_inputs

A dictionary of input values for WebhookInput nodes:

```json
{
  "webhook_inputs": {
    "prompt": "text value",
    "seed": 42,
    "cfg": 7.5,
    "use_feature": true,
    "image": "data:image/png;base64,...",
    "image_url": "https://example.com/image.png",
    "images": ["base64...", "https://..."],
    "audio": "data:audio/wav;base64,...",
    "params": {"key": "value"}
  }
}
```

## Webhook Events

### workflow.completed (Multipart)

Sent as multipart/form-data when execution completes successfully:

```
Content-Type: multipart/form-data; boundary=----WebhookBoundary

------WebhookBoundary
Content-Disposition: form-data; name="metadata"
Content-Type: application/json

{
  "event": "workflow.completed",
  "request_id": "req_abc123",
  "prompt_id": "comfy_12345",
  "timestamp": "2024-01-15T10:30:10.000Z",
  "status": "success",
  "output_count": 1,
  "file_count": 1,
  "outputs": [
    {
      "type": "image",
      "format": "png",
      "filename": "ComfyUI_00001_.png",
      "width": 1024,
      "height": 1024,
      "file_size_bytes": 1234567,
      "node_id": "9",
      "node_type": "SaveImage"
    }
  ],
  "execution_time_ms": 12345,
  "nodes_executed": 5
}
------WebhookBoundary
Content-Disposition: form-data; name="file_0"; filename="ComfyUI_00001_.png"
Content-Type: image/png

<binary PNG data>
------WebhookBoundary--
```

### workflow.error

Sent if execution fails:

```json
{
  "event": "workflow.error",
  "request_id": "req_abc123",
  "prompt_id": "comfy_12345",
  "timestamp": "2024-01-15T10:30:00.000Z",
  "status": "error",
  "messages": [
    {"type": "execution_error", "message": "CUDA out of memory", "node_id": "7"}
  ],
  "elapsed_ms": 5234
}
```

### workflow.started

Sent when execution begins (only when using WebhookReceiver node):

```json
{
  "event": "workflow.started",
  "request_id": "req_abc123",
  "prompt_id": "comfy_12345",
  "timestamp": "2024-01-15T10:30:00.000Z"
}
```

### workflow.progress

Sent during execution (if enabled, only with WebhookReceiver):

```json
{
  "event": "workflow.progress",
  "request_id": "req_abc123",
  "prompt_id": "comfy_12345",
  "node_id": "7",
  "node_type": "KSampler",
  "progress": 0.45,
  "message": "Sampling step 9/20",
  "elapsed_ms": 5234
}
```

## Example Webhook Receiver (Python/FastAPI)

```python
from fastapi import FastAPI, Request
import json

app = FastAPI()

@app.post("/webhook")
async def receive_webhook(request: Request):
    content_type = request.headers.get("content-type", "")

    if "multipart/form-data" in content_type:
        # Parse multipart (workflow completed with outputs)
        form = await request.form()
        metadata = json.loads(form["metadata"])

        print(f"Received {metadata['event']}: {metadata['output_count']} outputs")

        # Process each file
        for key, value in form.items():
            if key.startswith("file_"):
                content = await value.read()
                filename = value.filename
                print(f"  File: {filename} ({len(content)} bytes)")
                # Save or process file...

        return {"status": "received", "outputs": metadata["output_count"]}
    else:
        # JSON event (started, progress, error)
        data = await request.json()
        print(f"Received {data['event']}")
        return {"status": "received", "event": data["event"]}
```

## Nodes Reference

### Entry Point
- **Webhook Receiver** - Main entry point, extracts config and inputs

### Input Nodes (for dynamic workflows)
- **Webhook Text Input** - Extract text string
- **Webhook Texts Input (List)** - Extract list of strings
- **Webhook Int Input** - Extract integer
- **Webhook Float Input** - Extract float
- **Webhook Bool Input** - Extract boolean
- **Webhook Image Input** - Extract single image (base64/URL)
- **Webhook Images Input (Batch)** - Extract multiple images as batch
- **Webhook Audio Input** - Extract audio (base64/URL)
- **Webhook Mask Input** - Extract mask image
- **Webhook Video Input** - Extract video
- **Webhook JSON Input** - Extract JSON as string
- **Webhook Any Input** - Extract any type

### Output Nodes (optional, for manual control)
- **Webhook Send** - Manually send data to webhook
- **Webhook Send JSON** - Send JSON data to webhook

### Debug
- **Webhook Debug Info** - Display webhook context information

## Supported Output Types

The webhook system automatically detects and handles:

| Type | Extensions | Detected From |
|------|------------|---------------|
| Image | png, jpg, webp, gif | SaveImage, PreviewImage |
| Audio | flac, wav, mp3, ogg | SaveAudio |
| Video | mp4, webm, mov | VHS nodes, custom video nodes |
| 3D Mesh | glb, gltf, obj | 3D preview nodes |
| Text | - | ShowText, any text output |
| Latent | safetensors | SaveLatent |

**Custom nodes are supported!** Any node that outputs to the `ui` dict with standard patterns will be detected.

## Development

### Running Tests

```bash
cd comfy-http-webhook
python run_tests.py
```

### Project Structure

```
comfy-http-webhook/
├── __init__.py              # Node registration & interceptor init
├── run_tests.py             # Test runner
├── README.md                # This file
├── requirements.txt         # Dependencies
├── core/
│   ├── types.py             # Data types (WebhookContext, OutputInfo)
│   ├── client.py            # Async HTTP client with retry logic
│   ├── context.py           # Thread-safe context registry
│   └── interceptor.py       # Output interception (zero-config magic)
├── nodes/
│   ├── receiver.py          # WebhookReceiver node
│   ├── inputs.py            # All input extraction nodes
│   └── send.py              # Manual output nodes
├── processors/
│   ├── inputs.py            # Base64/URL decoding
│   └── outputs.py           # Output type detection
├── utils/
│   ├── mime.py              # MIME type utilities
│   └── validation.py        # URL and data validation
└── tests/
    └── ...                  # Test files
```

## How Zero-Config Works

The magic happens in `core/interceptor.py`:

1. **On module load**: Hooks into `PromptQueue.task_done()` method
2. **On workflow complete**: Checks if `extra_data` contains `webhook_config`
3. **If webhook configured**: Extracts all outputs from `history_result`
4. **Sends multipart POST**: Metadata JSON + all output files
5. **Background thread**: Non-blocking delivery with retry logic

This means ANY workflow works - no modifications needed!

## Troubleshooting

### Webhook not receiving data?

1. Check ComfyUI logs for webhook delivery messages
2. Verify `callback_url` is accessible from ComfyUI server
3. Check authentication headers are correct
4. Look for error events in your webhook endpoint

### Files not included in webhook?

1. Ensure output nodes are configured to save files (not just preview)
2. Check that files exist in output directory after workflow completes
3. Verify file permissions allow reading

## License

MIT License
