# ComfyUI HTTP Webhook Node - Implementation Plan

## Executive Summary

This document outlines the design and implementation plan for a production-quality HTTP webhook node system for ComfyUI. The system enables:

1. **Triggering workflows via HTTP** with dynamic variables
2. **Real-time progress updates** sent to external webhook endpoints
3. **Final output delivery** to callback URLs (images, audio, video, 3D, etc.)
4. **Completion notifications** with status and metadata

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Node Types](#node-types)
3. [Data Flow](#data-flow)
4. [Webhook Payload Specifications](#webhook-payload-specifications)
5. [HTTP Client Design](#http-client-design)
6. [Error Handling & Reliability](#error-handling--reliability)
7. [Output Type Support](#output-type-support)
8. [Security Considerations](#security-considerations)
9. [Edge Cases](#edge-cases)
10. [Testing Strategy](#testing-strategy)
11. [File Structure](#file-structure)
12. [Dependencies](#dependencies)

---

## 1. Architecture Overview

### High-Level Design

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           EXTERNAL SYSTEM                                    │
│  ┌─────────────┐     ┌─────────────────┐     ┌─────────────────────────┐   │
│  │ HTTP Client │────▶│ Webhook Receiver │◀────│ Status/Output Receiver  │   │
│  └─────────────┘     └─────────────────┘     └─────────────────────────┘   │
│         │                    ▲                          ▲                   │
└─────────│────────────────────│──────────────────────────│───────────────────┘
          │                    │                          │
          ▼                    │                          │
┌─────────────────────────────────────────────────────────────────────────────┐
│                              COMFYUI                                         │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                         WORKFLOW                                      │   │
│  │                                                                       │   │
│  │  ┌─────────────────┐                                                  │   │
│  │  │ WebhookConfig   │  Contains: callback_url, auth headers,           │   │
│  │  │ (Input Node)    │  request_id, custom metadata                     │   │
│  │  └────────┬────────┘                                                  │   │
│  │           │                                                           │   │
│  │           ▼                                                           │   │
│  │  ┌─────────────────┐     ┌─────────────────┐                         │   │
│  │  │ WebhookVariable │────▶│  Regular Nodes  │                         │   │
│  │  │ (Inject vars)   │     │  (KSampler etc) │                         │   │
│  │  └─────────────────┘     └────────┬────────┘                         │   │
│  │                                   │                                   │   │
│  │           ┌───────────────────────┼───────────────────────┐          │   │
│  │           ▼                       ▼                       ▼          │   │
│  │  ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐ │   │
│  │  │ WebhookOutput   │     │ WebhookOutput   │     │ WebhookOutput   │ │   │
│  │  │ (Image)         │     │ (Audio)         │     │ (Video/3D)      │ │   │
│  │  └────────┬────────┘     └────────┬────────┘     └────────┬────────┘ │   │
│  │           │                       │                       │          │   │
│  └───────────│───────────────────────│───────────────────────│──────────┘   │
│              │                       │                       │              │
│              ▼                       ▼                       ▼              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                    HTTP Client (Async with Retry)                     │   │
│  │  - Exponential backoff with jitter                                    │   │
│  │  - Circuit breaker pattern                                            │   │
│  │  - Request queuing and batching                                       │   │
│  │  - Connection pooling                                                 │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Key Design Principles

1. **Non-blocking**: All HTTP calls are async to not block the execution pipeline
2. **Reliable**: Retry logic with exponential backoff for transient failures
3. **Observable**: Detailed logging and error reporting
4. **Flexible**: Support for all output types without code changes
5. **Secure**: Support for authentication headers and HTTPS
6. **Idempotent**: Request IDs to prevent duplicate processing

---

## 2. Node Types

### 2.1 WebhookConfig Node

**Purpose**: Central configuration for webhook settings, shared across the workflow.

```python
class WebhookConfig:
    """
    Configures webhook settings for the entire workflow.
    This node should be placed once per workflow and connected to output nodes.
    """

    INPUTS:
        - callback_url: STRING (required) - Base URL for webhook callbacks
        - auth_header_name: STRING (optional) - Header name for auth (e.g., "Authorization")
        - auth_header_value: STRING (optional) - Header value (e.g., "Bearer token123")
        - request_id: STRING (optional) - Unique ID for this request (auto-generated if empty)
        - custom_metadata: STRING (optional) - JSON string with custom data to include in callbacks
        - send_progress: BOOLEAN (default: True) - Whether to send progress updates
        - progress_interval: FLOAT (default: 1.0) - Minimum seconds between progress updates
        - timeout_seconds: INT (default: 30) - HTTP request timeout
        - max_retries: INT (default: 3) - Maximum retry attempts
        - include_workflow: BOOLEAN (default: False) - Include workflow JSON in final callback

    OUTPUTS:
        - WEBHOOK_CONFIG: Custom type containing all config

    CATEGORY: "webhook"
    OUTPUT_NODE: False
```

### 2.2 WebhookVariable Nodes

**Purpose**: Inject dynamic variables from the API request into the workflow.

```python
class WebhookStringVariable:
    """String variable that can be set via webhook request."""

    INPUTS:
        - variable_name: STRING - Name of the variable (used in API request)
        - default_value: STRING - Default if not provided in request

    OUTPUTS:
        - STRING

    HIDDEN:
        - PROMPT - Access to find variable values

class WebhookIntVariable:
    """Integer variable that can be set via webhook request."""
    # Similar structure, outputs INT

class WebhookFloatVariable:
    """Float variable that can be set via webhook request."""
    # Similar structure, outputs FLOAT

class WebhookImageVariable:
    """Image variable - accepts base64 or URL in webhook request."""
    # Outputs IMAGE tensor

class WebhookSeedVariable:
    """Seed variable with special handling for -1 (random)."""
    # Outputs INT with seed semantics
```

### 2.3 WebhookOutput Nodes (OUTPUT_NODE = True)

**Purpose**: Intercept outputs and send to webhook endpoint.

```python
class WebhookImageOutput:
    """
    Saves images and sends them to the configured webhook.
    Supports multiple format options and compression levels.
    """

    INPUTS:
        - images: IMAGE (required)
        - webhook_config: WEBHOOK_CONFIG (required)
        - filename_prefix: STRING (default: "ComfyUI")
        - format: COMBO ["png", "jpg", "webp"] (default: "png")
        - quality: INT (0-100, default: 95) - For lossy formats
        - send_as: COMBO ["base64", "url", "multipart"] (default: "base64")
        - include_metadata: BOOLEAN (default: True)

    OUTPUTS: ()  # No outputs - this is a terminal node
    OUTPUT_NODE: True

class WebhookAudioOutput:
    """Sends audio to webhook endpoint."""

    INPUTS:
        - audio: AUDIO (required)
        - webhook_config: WEBHOOK_CONFIG (required)
        - format: COMBO ["flac", "mp3", "opus", "wav"] (default: "flac")
        - send_as: COMBO ["base64", "url"] (default: "base64")

class WebhookVideoOutput:
    """Sends video to webhook endpoint."""

    INPUTS:
        - video: VIDEO or IMAGE (for frame sequences)
        - webhook_config: WEBHOOK_CONFIG (required)
        - format: COMBO ["webm", "mp4"] (default: "webm")
        - fps: FLOAT (default: 24.0)

class WebhookMeshOutput:
    """Sends 3D mesh to webhook endpoint."""

    INPUTS:
        - mesh: MESH (required)
        - webhook_config: WEBHOOK_CONFIG (required)
        - format: COMBO ["glb", "obj"] (default: "glb")

class WebhookGenericOutput:
    """
    Generic output node for any data type.
    Serializes to JSON where possible.
    """

    INPUTS:
        - data: ANY (required)
        - webhook_config: WEBHOOK_CONFIG (required)
        - output_name: STRING (default: "output")
```

### 2.4 WebhookProgress Node (Optional)

**Purpose**: Send custom progress updates at specific points in the workflow.

```python
class WebhookProgressUpdate:
    """
    Sends a custom progress update to the webhook.
    Useful for marking milestones in complex workflows.
    """

    INPUTS:
        - trigger: ANY (required) - Pass-through to control execution order
        - webhook_config: WEBHOOK_CONFIG (required)
        - message: STRING - Progress message
        - progress_percent: FLOAT (0-100) - Optional progress percentage
        - custom_data: STRING - Optional JSON data

    OUTPUTS:
        - ANY - Passes through the trigger input
```

---

## 3. Data Flow

### 3.1 Request Flow (External → ComfyUI)

```
1. External System sends POST /prompt with:
   {
     "prompt": { ... workflow ... },
     "extra_data": {
       "webhook_variables": {
         "prompt_text": "a beautiful sunset",
         "seed": 12345,
         "input_image": "base64_or_url"
       }
     }
   }

2. WebhookVariable nodes extract values from extra_data.webhook_variables

3. Workflow executes normally with injected values
```

### 3.2 Callback Flow (ComfyUI → External)

```
1. On workflow start:
   POST {callback_url}/status
   {
     "event": "workflow.started",
     "request_id": "uuid",
     "prompt_id": "comfy_prompt_id",
     "timestamp": "ISO8601"
   }

2. During execution (if send_progress=True):
   POST {callback_url}/progress
   {
     "event": "workflow.progress",
     "request_id": "uuid",
     "prompt_id": "comfy_prompt_id",
     "node_id": "current_node",
     "progress": 0.45,
     "message": "Sampling step 9/20",
     "timestamp": "ISO8601"
   }

3. On each output:
   POST {callback_url}/output
   {
     "event": "output.ready",
     "request_id": "uuid",
     "prompt_id": "comfy_prompt_id",
     "output_type": "image",
     "output_index": 0,
     "total_outputs": 3,
     "data": { ... format-specific data ... },
     "timestamp": "ISO8601"
   }

4. On completion:
   POST {callback_url}/complete
   {
     "event": "workflow.completed",
     "request_id": "uuid",
     "prompt_id": "comfy_prompt_id",
     "status": "success",
     "outputs_sent": 3,
     "execution_time_ms": 12345,
     "timestamp": "ISO8601",
     "metadata": { ... custom metadata ... }
   }

5. On error:
   POST {callback_url}/error
   {
     "event": "workflow.error",
     "request_id": "uuid",
     "prompt_id": "comfy_prompt_id",
     "error": {
       "type": "execution_error",
       "message": "Out of memory",
       "node_id": "5",
       "node_type": "KSampler",
       "traceback": "..."
     },
     "timestamp": "ISO8601"
   }
```

---

## 4. Webhook Payload Specifications

### 4.1 Common Fields (All Events)

```json
{
  "event": "string",           // Event type identifier
  "request_id": "uuid",        // Client-provided or auto-generated
  "prompt_id": "string",       // ComfyUI's internal prompt ID
  "timestamp": "ISO8601",      // When the event occurred
  "version": "1.0"             // API version for future compatibility
}
```

### 4.2 Image Output Payload

```json
{
  "event": "output.ready",
  "output_type": "image",
  "output_index": 0,
  "total_outputs": 4,
  "data": {
    // Option 1: Base64
    "format": "png",
    "encoding": "base64",
    "content": "iVBORw0KGgoAAAANS...",
    "width": 1024,
    "height": 1024,

    // Option 2: URL (if ComfyUI is accessible)
    "format": "png",
    "encoding": "url",
    "url": "http://comfyui:8188/view?filename=output_00001.png&type=output",
    "width": 1024,
    "height": 1024,

    // Option 3: Multipart (sent separately)
    "format": "png",
    "encoding": "multipart",
    "multipart_id": "uuid",
    "width": 1024,
    "height": 1024
  },
  "metadata": {
    "filename": "ComfyUI_00001.png",
    "seed": 12345,
    "prompt": "a beautiful sunset"  // If include_metadata=True
  }
}
```

### 4.3 Audio Output Payload

```json
{
  "event": "output.ready",
  "output_type": "audio",
  "data": {
    "format": "flac",
    "encoding": "base64",
    "content": "ZkxhQwAAABIAAAA...",
    "sample_rate": 44100,
    "channels": 2,
    "duration_seconds": 5.2
  }
}
```

### 4.4 Video Output Payload

```json
{
  "event": "output.ready",
  "output_type": "video",
  "data": {
    "format": "webm",
    "encoding": "base64",
    "content": "GkXfo59ChoEBQveB...",
    "width": 1024,
    "height": 1024,
    "fps": 24,
    "duration_seconds": 4.0,
    "frame_count": 96
  }
}
```

### 4.5 3D Mesh Output Payload

```json
{
  "event": "output.ready",
  "output_type": "mesh",
  "data": {
    "format": "glb",
    "encoding": "base64",
    "content": "Z2xURgIAAAD...",
    "vertex_count": 12500,
    "face_count": 25000
  }
}
```

---

## 5. HTTP Client Design

### 5.1 Core Client Class

```python
class WebhookClient:
    """
    Production-grade async HTTP client for webhook delivery.

    Features:
    - Connection pooling via aiohttp.ClientSession
    - Exponential backoff with jitter
    - Circuit breaker for failing endpoints
    - Request queuing for rate limiting
    - Comprehensive logging
    """

    def __init__(
        self,
        timeout: float = 30.0,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        jitter_factor: float = 0.1,
    ):
        self.session: Optional[aiohttp.ClientSession] = None
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.jitter_factor = jitter_factor
        self._circuit_breaker = CircuitBreaker()

    async def send_webhook(
        self,
        url: str,
        payload: dict,
        headers: Optional[dict] = None,
        method: str = "POST",
    ) -> WebhookResult:
        """Send webhook with retry logic."""

    async def send_multipart(
        self,
        url: str,
        payload: dict,
        files: dict[str, bytes],
        headers: Optional[dict] = None,
    ) -> WebhookResult:
        """Send multipart request with files."""
```

### 5.2 Retry Strategy

```python
async def _execute_with_retry(self, request_func) -> WebhookResult:
    """
    Execute request with exponential backoff.

    Retry schedule (with base_delay=1.0):
    - Attempt 1: Immediate
    - Attempt 2: ~1 second (with jitter)
    - Attempt 3: ~2 seconds
    - Attempt 4: ~4 seconds

    Retryable status codes: 408, 429, 500, 502, 503, 504
    Non-retryable: 400, 401, 403, 404, 422
    """
    last_exception = None

    for attempt in range(self.max_retries + 1):
        try:
            if attempt > 0:
                delay = self._calculate_delay(attempt)
                await asyncio.sleep(delay)

            response = await request_func()

            if response.status < 400:
                return WebhookResult(success=True, status=response.status)

            if response.status in RETRYABLE_STATUS_CODES:
                last_exception = WebhookError(f"HTTP {response.status}")
                continue

            # Non-retryable error
            return WebhookResult(
                success=False,
                status=response.status,
                error=f"HTTP {response.status}"
            )

        except aiohttp.ClientError as e:
            last_exception = e
            continue

    return WebhookResult(success=False, error=str(last_exception))

def _calculate_delay(self, attempt: int) -> float:
    """Calculate delay with exponential backoff and jitter."""
    delay = min(self.base_delay * (2 ** (attempt - 1)), self.max_delay)
    jitter = delay * self.jitter_factor * random.random()
    return delay + jitter
```

### 5.3 Circuit Breaker

```python
class CircuitBreaker:
    """
    Prevents overwhelming failing services.

    States:
    - CLOSED: Normal operation
    - OPEN: Failing fast (not sending requests)
    - HALF_OPEN: Testing if service recovered
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        half_open_max_calls: int = 3,
    ):
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout

    def can_execute(self) -> bool:
        """Check if request should be attempted."""

    def record_success(self):
        """Record successful request."""

    def record_failure(self):
        """Record failed request."""
```

---

## 6. Error Handling & Reliability

### 6.1 Error Categories

| Category | Handling | Example |
|----------|----------|---------|
| Network Errors | Retry with backoff | Connection refused, timeout |
| Server Errors (5xx) | Retry with backoff | 500, 502, 503, 504 |
| Rate Limiting (429) | Retry with longer delay | Too many requests |
| Client Errors (4xx) | No retry, log error | 400, 401, 403 |
| Validation Errors | No retry, report to user | Invalid URL format |

### 6.2 Error Reporting

```python
class WebhookErrorReporter:
    """
    Reports webhook errors to the ComfyUI frontend.
    Also logs to file for debugging.
    """

    def report_error(
        self,
        error_type: str,
        message: str,
        context: dict,
        recoverable: bool = True,
    ):
        # 1. Log to file
        logging.error(f"Webhook error: {error_type} - {message}", extra=context)

        # 2. Send to frontend via WebSocket
        server.send_sync("webhook_error", {
            "type": error_type,
            "message": message,
            "recoverable": recoverable,
            "timestamp": datetime.now().isoformat(),
        })

        # 3. Store in execution history
        # ... for later retrieval
```

### 6.3 Graceful Degradation

When webhook delivery fails after all retries:

1. **Continue execution**: Workflow completes normally
2. **Save outputs locally**: Files still saved to output directory
3. **Queue for retry**: Optional background retry queue
4. **Report failure**: Clear error message to frontend

```python
class WebhookDeliveryQueue:
    """
    Persistent queue for failed webhook deliveries.
    Retries periodically in background.
    """

    async def enqueue_failed(self, webhook_data: dict):
        """Add failed delivery to retry queue."""

    async def process_queue(self):
        """Background task to retry failed deliveries."""
```

---

## 7. Output Type Support

### 7.1 Image Processing

```python
def process_image_output(
    images: torch.Tensor,
    format: str,
    quality: int,
    send_as: str,
) -> list[OutputData]:
    """
    Process image tensor(s) for webhook delivery.

    Supports:
    - PNG: Lossless, with metadata embedding
    - JPEG: Lossy, smaller size
    - WebP: Modern format, good compression
    """
    outputs = []

    for i, image in enumerate(images):
        # Convert tensor to PIL Image
        img_np = (image.cpu().numpy() * 255).astype(np.uint8)
        pil_image = Image.fromarray(img_np)

        # Encode based on format
        buffer = io.BytesIO()
        if format == "png":
            pil_image.save(buffer, format="PNG", compress_level=4)
        elif format == "jpg":
            pil_image.save(buffer, format="JPEG", quality=quality)
        elif format == "webp":
            pil_image.save(buffer, format="WEBP", quality=quality)

        # Prepare output based on send_as mode
        if send_as == "base64":
            content = base64.b64encode(buffer.getvalue()).decode()
            outputs.append(OutputData(
                encoding="base64",
                content=content,
                width=pil_image.width,
                height=pil_image.height,
            ))
        elif send_as == "url":
            # Save locally and provide URL
            filename = save_to_output_dir(buffer, format)
            outputs.append(OutputData(
                encoding="url",
                url=f"/view?filename={filename}&type=output",
            ))

    return outputs
```

### 7.2 Audio Processing

```python
def process_audio_output(
    audio: dict,  # {"waveform": tensor, "sample_rate": int}
    format: str,
) -> OutputData:
    """
    Process audio for webhook delivery.

    Supports:
    - FLAC: Lossless, recommended
    - MP3: Lossy, wide compatibility
    - Opus: Modern, efficient
    - WAV: Uncompressed, large
    """
    waveform = audio["waveform"]
    sample_rate = audio["sample_rate"]

    buffer = io.BytesIO()

    # Use torchaudio or soundfile for encoding
    # ... encoding logic based on format

    return OutputData(
        encoding="base64",
        content=base64.b64encode(buffer.getvalue()).decode(),
        sample_rate=sample_rate,
        duration_seconds=waveform.shape[-1] / sample_rate,
    )
```

### 7.3 Video Processing

```python
def process_video_output(
    frames: torch.Tensor,  # [N, H, W, C]
    format: str,
    fps: float,
) -> OutputData:
    """
    Process video frames for webhook delivery.

    Uses PyAV for encoding:
    - WebM: VP9 or AV1 codec
    - MP4: H.264 codec
    """
    buffer = io.BytesIO()
    container = av.open(buffer, mode='w', format=format)

    codec = "libvpx-vp9" if format == "webm" else "libx264"
    stream = container.add_stream(codec, rate=fps)
    # ... encoding logic

    return OutputData(
        encoding="base64",
        content=base64.b64encode(buffer.getvalue()).decode(),
        fps=fps,
        frame_count=frames.shape[0],
        duration_seconds=frames.shape[0] / fps,
    )
```

### 7.4 3D Mesh Processing

```python
def process_mesh_output(
    mesh: MeshData,  # Custom mesh type
    format: str,
) -> OutputData:
    """
    Process 3D mesh for webhook delivery.

    Supports:
    - GLB: Binary glTF, efficient
    - OBJ: Text-based, wide compatibility
    """
    buffer = io.BytesIO()

    if format == "glb":
        # Use trimesh or pygltflib
        save_glb(mesh.vertices, mesh.faces, buffer)
    elif format == "obj":
        save_obj(mesh.vertices, mesh.faces, buffer)

    return OutputData(
        encoding="base64",
        content=base64.b64encode(buffer.getvalue()).decode(),
        vertex_count=mesh.vertices.shape[0],
        face_count=mesh.faces.shape[0],
    )
```

---

## 8. Security Considerations

### 8.1 Authentication

```python
class WebhookAuth:
    """
    Supports multiple authentication methods.
    """

    # Method 1: Bearer Token
    headers = {"Authorization": f"Bearer {token}"}

    # Method 2: API Key
    headers = {"X-API-Key": api_key}

    # Method 3: Basic Auth
    auth = aiohttp.BasicAuth(username, password)

    # Method 4: HMAC Signature (for webhook verification)
    def sign_payload(self, payload: bytes, secret: str) -> str:
        signature = hmac.new(
            secret.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()
        return f"sha256={signature}"
```

### 8.2 Input Validation

```python
def validate_webhook_url(url: str) -> bool:
    """
    Validate webhook URL for security.

    Checks:
    - Valid URL format
    - HTTPS preferred (warn if HTTP)
    - No localhost/private IPs in production
    - No file:// or other dangerous schemes
    """
    parsed = urlparse(url)

    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Invalid URL scheme: {parsed.scheme}")

    if parsed.scheme == "http":
        logging.warning("Using HTTP for webhook - HTTPS recommended")

    # Check for private IPs (configurable)
    # ...

    return True
```

### 8.3 Sensitive Data Handling

```python
# Never log sensitive data
def sanitize_for_logging(data: dict) -> dict:
    """Remove sensitive fields before logging."""
    sensitive_keys = {"auth_header_value", "api_key", "token", "password"}
    return {
        k: "[REDACTED]" if k in sensitive_keys else v
        for k, v in data.items()
    }
```

---

## 9. Edge Cases

### 9.1 Large Payloads

**Problem**: Images/videos can be very large, exceeding typical payload limits.

**Solutions**:
1. **Chunked upload**: Split large files into chunks
2. **URL mode**: Upload to temp storage, send URL instead
3. **Compression**: Reduce quality for very large outputs
4. **Size limit warning**: Warn users when payload exceeds threshold

```python
MAX_PAYLOAD_SIZE = 10 * 1024 * 1024  # 10MB default

def check_payload_size(data: bytes) -> bool:
    if len(data) > MAX_PAYLOAD_SIZE:
        logging.warning(f"Payload size {len(data)} exceeds limit {MAX_PAYLOAD_SIZE}")
        return False
    return True
```

### 9.2 Multiple Output Nodes

**Problem**: Workflow has multiple output nodes, need to track completion.

**Solution**: Coordinator tracks all outputs and sends final completion only when all are done.

```python
class OutputCoordinator:
    """Coordinates multiple output nodes in a workflow."""

    def __init__(self, total_outputs: int):
        self.total_outputs = total_outputs
        self.completed_outputs = 0
        self.output_results = []

    def output_completed(self, output_data: OutputData):
        self.completed_outputs += 1
        self.output_results.append(output_data)

        if self.completed_outputs == self.total_outputs:
            self.send_completion()
```

### 9.3 Workflow Interruption

**Problem**: User cancels workflow mid-execution.

**Solution**: Send interrupted event with partial results.

```python
async def handle_interruption(self):
    await self.webhook_client.send_webhook(
        url=self.callback_url,
        payload={
            "event": "workflow.interrupted",
            "request_id": self.request_id,
            "outputs_completed": len(self.completed_outputs),
            "outputs_total": self.total_outputs,
        }
    )
```

### 9.4 Webhook Endpoint Down

**Problem**: Callback URL is unreachable.

**Solutions**:
1. Retry with exponential backoff
2. Store failed deliveries for later retry
3. Continue workflow execution regardless
4. Report error to frontend

### 9.5 Concurrent Workflows

**Problem**: Multiple workflows using webhooks simultaneously.

**Solution**: Each workflow has isolated state via request_id.

```python
# Global registry of active webhook contexts
_active_contexts: dict[str, WebhookContext] = {}

def get_context(prompt_id: str) -> Optional[WebhookContext]:
    return _active_contexts.get(prompt_id)
```

### 9.6 Memory Pressure

**Problem**: Large outputs consume significant memory during encoding.

**Solutions**:
1. Stream encoding where possible
2. Process images one at a time (not as batch)
3. Clear references immediately after sending
4. Option to skip in-memory encoding (URL mode)

---

## 10. Testing Strategy

### 10.1 Unit Tests

```python
# test_webhook_client.py
class TestWebhookClient:
    async def test_successful_delivery(self):
        """Test successful webhook delivery."""

    async def test_retry_on_server_error(self):
        """Test retry behavior on 5xx errors."""

    async def test_no_retry_on_client_error(self):
        """Test no retry on 4xx errors."""

    async def test_exponential_backoff(self):
        """Test backoff timing."""

    async def test_circuit_breaker(self):
        """Test circuit breaker activation."""
```

### 10.2 Integration Tests

```python
# test_webhook_nodes.py
class TestWebhookNodes:
    def test_webhook_config_creation(self):
        """Test WebhookConfig node creates valid config."""

    def test_image_output_encoding(self):
        """Test image encoding in various formats."""

    def test_full_workflow_execution(self):
        """Test complete workflow with webhook output."""
```

### 10.3 End-to-End Tests

```python
# test_e2e.py
class TestEndToEnd:
    async def test_webhook_receives_all_events(self):
        """
        1. Start mock webhook server
        2. Submit workflow via API
        3. Verify all expected events received
        4. Check payload structure
        """

    async def test_error_handling(self):
        """Test error events are properly sent."""

    async def test_retry_behavior(self):
        """Test retries when webhook initially fails."""
```

### 10.4 Load Tests

```python
# test_load.py
class TestLoad:
    async def test_concurrent_workflows(self):
        """Test multiple workflows with webhooks simultaneously."""

    async def test_large_batch_output(self):
        """Test handling of large image batches."""

    async def test_rapid_progress_updates(self):
        """Test progress update throttling."""
```

---

## 11. File Structure

```
custom_nodes/comfy-http-webhook/
├── __init__.py                 # Node registration
├── PLAN.md                     # This document
├── TODOs.md                    # Implementation checklist
├── README.md                   # User documentation
├── requirements.txt            # Dependencies
│
├── nodes/
│   ├── __init__.py
│   ├── config_node.py          # WebhookConfig node
│   ├── variable_nodes.py       # WebhookVariable nodes
│   ├── output_nodes.py         # WebhookOutput nodes
│   └── progress_node.py        # WebhookProgressUpdate node
│
├── core/
│   ├── __init__.py
│   ├── client.py               # WebhookClient
│   ├── circuit_breaker.py      # CircuitBreaker
│   ├── coordinator.py          # OutputCoordinator
│   ├── payloads.py             # Payload builders
│   └── types.py                # Custom types (WebhookConfig, etc.)
│
├── processors/
│   ├── __init__.py
│   ├── image.py                # Image processing
│   ├── audio.py                # Audio processing
│   ├── video.py                # Video processing
│   └── mesh.py                 # 3D mesh processing
│
├── utils/
│   ├── __init__.py
│   ├── validation.py           # URL/input validation
│   ├── encoding.py             # Base64/encoding utilities
│   └── logging.py              # Logging utilities
│
└── tests/
    ├── __init__.py
    ├── test_client.py
    ├── test_nodes.py
    ├── test_processors.py
    ├── test_e2e.py
    └── mock_server.py          # Mock webhook server for testing
```

---

## 12. Dependencies

### Required

```
aiohttp>=3.8.0          # Async HTTP client
pydantic>=2.0.0         # Data validation (optional but recommended)
```

### Optional (for extended format support)

```
av>=10.0.0              # Video encoding (already in ComfyUI)
soundfile>=0.12.0       # Audio encoding (already in ComfyUI for some formats)
trimesh>=4.0.0          # 3D mesh handling (optional)
```

### Development

```
pytest>=7.0.0           # Testing
pytest-asyncio>=0.21.0  # Async test support
aiohttp-test>=0.0.10    # Mock server for testing
```

---

## Next Steps

1. Review this plan and provide feedback
2. See TODOs.md for detailed implementation checklist
3. Begin implementation with core client and config node
4. Iterate based on testing and feedback

---

## References

- [ComfyUI Custom Nodes Guide](https://docs.comfy.org/development/core-concepts/custom-nodes)
- [ComfyUI API Documentation](https://docs.comfy.org/development/comfyui-server)
- [aiohttp Documentation](https://docs.aiohttp.org/)
- [Webhook Best Practices](https://www.svix.com/resources/webhook-best-practices/)
- [Existing Implementation: SaladTechnologies/comfyui-api](https://github.com/SaladTechnologies/comfyui-api)
- [Existing Implementation: ComfyUI-Save-Image-Callback](https://github.com/WUYUDING2583/ComfyUI-Save-Image-Callback)
