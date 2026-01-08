# ComfyUI HTTP Webhook Node

A production-quality custom node package for ComfyUI that enables HTTP webhook integration for triggering workflows and receiving outputs.

## Features

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

### 1. Add WebhookReceiver to Your Workflow

The `WebhookReceiver` node is the entry point for webhook-triggered workflows. It extracts configuration and input variables from the API request.

### 2. Connect WebhookInput Nodes

Use the various `WebhookInput` nodes to extract specific variables:

- `WebhookTextInput` - Extract text strings
- `WebhookIntInput` - Extract integers (seeds, steps, etc.)
- `WebhookFloatInput` - Extract floats (cfg, denoise, etc.)
- `WebhookBoolInput` - Extract booleans
- `WebhookImageInput` - Extract images (base64 or URL)
- `WebhookImagesInput` - Extract multiple images as a batch
- `WebhookAudioInput` - Extract audio (base64 or URL)
- `WebhookMaskInput` - Extract masks
- `WebhookJSONInput` - Extract JSON data as string

### 3. Connect to Regular Workflow Nodes

Connect the outputs to your regular ComfyUI nodes (KSampler, VAE Decode, etc.).

### 4. Use Standard Output Nodes

**Important**: You don't need special output nodes! The webhook system automatically intercepts outputs from standard nodes like `SaveImage`, `SaveAudio`, etc.

### 5. Submit via API

```json
POST /prompt
{
  "prompt": { /* your workflow JSON */ },
  "extra_data": {
    "webhook_config": {
      "callback_url": "https://api.example.com/webhook",
      "auth_header": "Authorization",
      "auth_value": "Bearer your-token-here",
      "request_id": "req_abc123",
      "send_progress": true
    },
    "webhook_inputs": {
      "prompt": "a beautiful sunset over mountains, 8k, detailed",
      "negative": "blurry, low quality",
      "seed": 42,
      "cfg": 7.5,
      "steps": 30,
      "image": "data:image/png;base64,iVBORw0KGgo...",
      "use_hires": true
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
| `send_progress` | boolean | true | Send progress events during execution |
| `progress_interval_ms` | integer | 1000 | Minimum interval between progress events |
| `timeout_seconds` | integer | 60 | Request timeout for webhook calls |
| `max_retries` | integer | 3 | Maximum retry attempts on failure |

### webhook_inputs

A dictionary of input values that can be extracted using WebhookInput nodes:

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

### workflow.started
Sent when execution begins.

```json
{
  "event": "workflow.started",
  "request_id": "req_abc123",
  "prompt_id": "comfy_12345",
  "timestamp": "2024-01-15T10:30:00.000Z"
}
```

### workflow.progress
Sent during execution (if enabled).

```json
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

### output.batch (Multipart)
Sent as multipart/form-data when execution completes:

```
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
  "execution_time_ms": 12345
}
------WebhookBoundary
Content-Disposition: form-data; name="file_0"; filename="ComfyUI_00001_.png"
Content-Type: image/png

<binary PNG data>
------WebhookBoundary--
```

### workflow.error
Sent if execution fails.

```json
{
  "event": "workflow.error",
  "request_id": "req_abc123",
  "prompt_id": "comfy_12345",
  "timestamp": "2024-01-15T10:30:00.000Z",
  "error": {
    "type": "execution_error",
    "message": "CUDA out of memory",
    "node_id": "7",
    "node_type": "KSampler"
  },
  "elapsed_ms": 5234
}
```

## Nodes Reference

### Entry Point
- **Webhook Receiver** - Main entry point, extracts config and inputs

### Input Nodes
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

### Output Nodes
- **Webhook Send** - Manually send data to webhook
- **Webhook Send JSON** - Send JSON data to webhook

### Debug
- **Webhook Debug Info** - Display webhook context information

## Example Receiver (Python/FastAPI)

```python
from fastapi import FastAPI, Request, UploadFile, Form
import json

app = FastAPI()

@app.post("/webhook")
async def receive_webhook(request: Request):
    content_type = request.headers.get("content-type", "")

    if "multipart/form-data" in content_type:
        # Parse multipart
        form = await request.form()
        metadata = json.loads(form["metadata"])

        # Process files
        for key, value in form.items():
            if key.startswith("file_"):
                # value is an UploadFile
                content = await value.read()
                # Save or process file...

        return {"status": "received", "event": metadata["event"]}
    else:
        # JSON event
        data = await request.json()
        return {"status": "received", "event": data["event"]}
```

## Development

### Running Tests

```bash
cd comfy-http-webhook
pip install pytest pytest-asyncio
pytest tests/ -v
```

### Project Structure

```
comfy-http-webhook/
├── __init__.py              # Node registration
├── PLAN.md                  # Architecture documentation
├── TODOs.md                 # Implementation checklist
├── README.md                # This file
├── requirements.txt         # Dependencies
├── core/
│   ├── types.py             # Data types
│   ├── client.py            # HTTP client
│   ├── context.py           # Context management
│   └── interceptor.py       # Output interception
├── nodes/
│   ├── receiver.py          # WebhookReceiver node
│   ├── inputs.py            # Input nodes
│   └── send.py              # Output nodes
├── processors/
│   ├── inputs.py            # Input processing
│   └── outputs.py           # Output detection
├── utils/
│   ├── mime.py              # MIME utilities
│   └── validation.py        # Validation utilities
└── tests/
    └── ...                  # Test files
```

## Documentation

- [Architecture & Design](./PLAN.md) - Detailed system design
- [Implementation Checklist](./TODOs.md) - Feature checklist

## License

MIT License
