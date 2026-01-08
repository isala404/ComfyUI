# ComfyUI HTTP Webhook Node - Implementation Checklist

This document provides a comprehensive, prioritized checklist for implementing the HTTP webhook node system from zero to production.

**Key Design Principles:**
- **Multipart-First**: ALL outputs sent as multipart/form-data
- **Universal Output Interception**: Works with ANY output node (built-in + custom)
- **Comprehensive Inputs**: Text, images (multiple), audio, video, masks, JSON, embeddings
- **Non-Blocking**: All HTTP operations are async
- **Zero-Config Outputs**: No need to replace output nodes

---

## Phase 1: Project Setup & Foundation

### 1.1 Project Structure
- [ ] Create `comfy-http-webhook/` directory at repo root
- [ ] Create `__init__.py` with `NODE_CLASS_MAPPINGS` and `NODE_DISPLAY_NAME_MAPPINGS`
- [ ] Create `requirements.txt` with dependencies (aiohttp>=3.8.0)
- [ ] Create `.gitignore` for Python projects
- [ ] Create `README.md` with basic documentation
- [ ] Create `pyproject.toml` for proper packaging (optional)

### 1.2 Core Types & Data Structures
- [ ] Create `core/types.py`
  - [ ] Define `WebhookContext` dataclass
    - [ ] `callback_url: str`
    - [ ] `request_id: str`
    - [ ] `auth_header: Optional[str]`
    - [ ] `auth_value: Optional[str]`
    - [ ] `send_progress: bool`
    - [ ] `timeout: int`
    - [ ] `max_retries: int`
    - [ ] `inputs: dict`
    - [ ] `prompt_id: str`
  - [ ] Define `WebhookResult` dataclass
  - [ ] Define `OutputInfo` dataclass
    - [ ] `type: str` (image, audio, video, mesh, text, latent, unknown)
    - [ ] `filename: Optional[str]`
    - [ ] `subfolder: Optional[str]`
    - [ ] `folder_type: Optional[str]`
    - [ ] `mime_type: str`
    - [ ] `inline_content: Optional[str]`
    - [ ] `to_dict() -> dict` method
  - [ ] Define `WebhookEvent` enum (started, progress, output_ready, output_batch, completed, error, interrupted)

### 1.3 Utility Functions
- [ ] Create `utils/validation.py`
  - [ ] Implement `validate_url(url: str) -> bool`
  - [ ] Implement `sanitize_for_logging(data: dict) -> dict`
  - [ ] Add URL scheme validation (http/https only)
  - [ ] Add optional private IP blocking
- [ ] Create `utils/mime.py`
  - [ ] Implement `guess_mime_type(filename: str) -> str`
  - [ ] Define MIME type mappings for all supported formats
- [ ] Create `utils/logging.py`
  - [ ] Set up structured logging for webhook operations
  - [ ] Add debug mode toggle

---

## Phase 2: Input Processing System

### 2.1 Input Processor Core
- [ ] Create `processors/inputs.py`
  - [ ] Implement `WebhookInputProcessor` class
    - [ ] `async process_inputs(webhook_inputs: dict) -> dict`
    - [ ] `_is_base64_image(value: str) -> bool`
    - [ ] `_is_base64_audio(value: str) -> bool`
    - [ ] `_is_url(value: str) -> bool`
    - [ ] `_is_image_data(value: str) -> bool`

### 2.2 Image Input Processing
- [ ] Implement `async _decode_base64_image(data: str) -> torch.Tensor`
  - [ ] Handle data URL prefix stripping (`data:image/png;base64,...`)
  - [ ] Support PNG, JPEG, WebP formats
  - [ ] Handle EXIF orientation via `ImageOps.exif_transpose`
  - [ ] Convert to RGB mode
  - [ ] Convert to tensor [1, H, W, C] with values 0-1
- [ ] Implement `async _download_and_decode(url: str) -> torch.Tensor`
  - [ ] Async download with aiohttp
  - [ ] Timeout handling (30s default)
  - [ ] Same decoding as base64

### 2.3 Multiple Images (Array Input)
- [ ] Implement `async _process_array(items: list) -> Union[torch.Tensor, list]`
  - [ ] Detect if all items are images
  - [ ] Process each image (base64 or URL)
  - [ ] Stack into batch tensor [N, H, W, C]
- [ ] Handle mixed-size images
  - [ ] Implement `batch_images_mixed_sizes()` with padding

### 2.4 Audio Input Processing
- [ ] Implement `async _decode_base64_audio(data: str) -> dict`
  - [ ] Handle data URL prefix stripping
  - [ ] Support WAV, MP3, FLAC, OGG formats
  - [ ] Return `{"waveform": tensor, "sample_rate": int}` format
  - [ ] Resample to 44100 Hz if needed

### 2.5 Video Input Processing
- [ ] Implement `async _decode_video(data: str) -> VIDEO`
  - [ ] Handle base64 video data
  - [ ] Handle video URLs
  - [ ] Extract frames using av or decord
  - [ ] Return VIDEO type tensor

### 2.6 Mask Input Processing
- [ ] Implement `async _decode_mask(data: str) -> torch.Tensor`
  - [ ] Decode image (base64 or URL)
  - [ ] Convert to grayscale
  - [ ] Return MASK tensor [1, H, W]

### 2.7 Other Input Types
- [ ] Implement JSON data handling (dict → serialized string)
- [ ] Implement passthrough for:
  - [ ] Plain strings
  - [ ] Integers
  - [ ] Floats
  - [ ] Booleans
  - [ ] Model references (checkpoint, lora, embedding names)

### 2.8 Input Processing Tests
- [ ] Create `tests/test_inputs.py`
  - [ ] Test base64 PNG image decode
  - [ ] Test base64 JPEG image decode
  - [ ] Test URL image download and decode
  - [ ] Test multiple images batching
  - [ ] Test mixed-size images batching
  - [ ] Test base64 audio decode
  - [ ] Test audio URL download
  - [ ] Test mask decode
  - [ ] Test JSON serialization
  - [ ] Test passthrough types

---

## Phase 3: Output Detection System

### 3.1 Output Detection
- [ ] Create `processors/outputs.py`
  - [ ] Implement `detect_output_type(ui_output: dict) -> list[OutputInfo]`
  - [ ] Handle `{"images": [{filename, subfolder, type}, ...]}` pattern
  - [ ] Handle `{"audio": [{filename, subfolder, type}, ...]}` pattern
  - [ ] Handle `{"video": [{filename, subfolder, type}, ...]}` pattern
  - [ ] Handle `{"3d": [{filename, subfolder, type}, ...]}` pattern
  - [ ] Handle `{"latents": [{filename, subfolder, type}, ...]}` pattern
  - [ ] Handle `{"text": (value,)}` pattern (tuple)
  - [ ] Handle `{"result": [...]}` pattern (3D preview)
  - [ ] Handle unknown patterns with fallback

### 3.2 File Path Resolution
- [ ] Implement `get_output_path(filename, subfolder, folder_type) -> str`
  - [ ] Handle "output" folder type
  - [ ] Handle "temp" folder type
  - [ ] Handle "input" folder type
  - [ ] Resolve absolute paths correctly

### 3.3 MIME Type Detection
- [ ] Implement comprehensive MIME type mapping
  - [ ] `.png` → `image/png`
  - [ ] `.jpg`, `.jpeg` → `image/jpeg`
  - [ ] `.webp` → `image/webp`
  - [ ] `.flac` → `audio/flac`
  - [ ] `.mp3` → `audio/mpeg`
  - [ ] `.wav` → `audio/wav`
  - [ ] `.opus`, `.ogg` → `audio/ogg`
  - [ ] `.mp4` → `video/mp4`
  - [ ] `.webm` → `video/webm`
  - [ ] `.glb` → `model/gltf-binary`
  - [ ] `.obj` → `text/plain`
  - [ ] `.latent` → `application/octet-stream`

### 3.4 Output Detection Tests
- [ ] Create `tests/test_outputs.py`
  - [ ] Test image output detection
  - [ ] Test audio output detection
  - [ ] Test video output detection
  - [ ] Test 3D mesh output detection
  - [ ] Test latent output detection
  - [ ] Test text output detection
  - [ ] Test 3D preview (result) detection
  - [ ] Test unknown format fallback
  - [ ] Test multiple outputs from single node

---

## Phase 4: HTTP Client Implementation

### 4.1 Multipart Client Core
- [ ] Create `core/client.py`
  - [ ] Implement `WebhookClient` class
    - [ ] `__init__(timeout, max_retries, base_delay, max_delay, jitter_factor)`
    - [ ] `async get_session() -> aiohttp.ClientSession` (lazy init)
    - [ ] `async close()` for cleanup

### 4.2 Session Management
- [ ] Implement connection pooling
  - [ ] `TCPConnector(limit=10, limit_per_host=5, keepalive_timeout=30)`
- [ ] Implement proper session lifecycle
- [ ] Handle session recreation on close

### 4.3 JSON Requests
- [ ] Implement `async send_json(url, payload, headers) -> WebhookResult`
  - [ ] For progress events, errors

### 4.4 Multipart Requests (In-Memory)
- [ ] Implement `async send_multipart(url, metadata, files, headers) -> WebhookResult`
  - [ ] Build `aiohttp.FormData`
  - [ ] Add metadata as JSON part with `content_type="application/json"`
  - [ ] Add files with proper `filename` and `content_type`
  - [ ] Files: `list[tuple[name, filename, bytes, mime_type]]`

### 4.5 Multipart Requests (Streaming)
- [ ] Implement `async send_multipart_streaming(url, metadata, file_paths, headers)`
  - [ ] Use `aiohttp.MultipartWriter` for disk streaming
  - [ ] Use `aiohttp.payload.FilePayload` for each file
  - [ ] For files > 50MB threshold

### 4.6 Retry Logic
- [ ] Implement `async _execute_with_retry(request_func) -> WebhookResult`
- [ ] Implement `_calculate_delay(attempt) -> float`
  - [ ] Exponential: `base_delay * (2 ** (attempt - 1))`
  - [ ] Cap at `max_delay`
  - [ ] Add jitter: `delay * jitter_factor * (random * 2 - 1)`
- [ ] Define retryable status codes: 408, 429, 500, 502, 503, 504
- [ ] Define non-retryable status codes: 400, 401, 403, 404, 422
- [ ] Handle `aiohttp.ClientError` exceptions
- [ ] Handle `asyncio.TimeoutError`
- [ ] Log retry attempts

### 4.7 Client Tests
- [ ] Create `tests/test_client.py`
  - [ ] Test successful JSON delivery
  - [ ] Test successful multipart delivery
  - [ ] Test retry on 500 errors
  - [ ] Test retry on 503 errors
  - [ ] Test no retry on 400 errors
  - [ ] Test exponential backoff timing
  - [ ] Test jitter randomization
  - [ ] Test timeout handling
  - [ ] Test connection error handling
  - [ ] Test session reuse
  - [ ] Test streaming multipart

---

## Phase 5: Output Interception System

### 5.1 Interceptor Core
- [ ] Create `core/interceptor.py`
  - [ ] Store `_original_task_done` global
  - [ ] Implement `install_output_interceptor()`
  - [ ] Implement `_intercepted_task_done(self, item_id, history_result, status, process_item)`

### 5.2 Context Registry
- [ ] Implement `_webhook_contexts: dict[str, WebhookContext]` registry
- [ ] Implement `register_webhook_context(context)`
- [ ] Implement `get_webhook_context(prompt_id) -> Optional[WebhookContext]`
- [ ] Implement `unregister_webhook_context(prompt_id)`
- [ ] Add cleanup on workflow completion

### 5.3 Output Processing
- [ ] Implement `async _send_webhook_outputs(webhook_config, prompt_id, outputs, status)`
  - [ ] Iterate all output nodes in `outputs` dict
  - [ ] Call `detect_output_type()` for each node's UI output
  - [ ] Read files from disk using `get_output_path()`
  - [ ] Build metadata payload
  - [ ] Build files list
  - [ ] Send via `client.send_multipart()`

### 5.4 Auth Header Construction
- [ ] Implement `_get_auth_headers(webhook_config) -> dict`
  - [ ] Handle `auth_header` + `auth_value` from config
  - [ ] Support Bearer tokens
  - [ ] Support API keys

### 5.5 Interceptor Installation
- [ ] Update `__init__.py` to call `install_output_interceptor()` on load
- [ ] Ensure interceptor survives ComfyUI reloads
- [ ] Add uninstall capability for testing

### 5.6 Interceptor Tests
- [ ] Create `tests/test_interceptor.py`
  - [ ] Test interceptor installation
  - [ ] Test context registration
  - [ ] Test output capture from SaveImage
  - [ ] Test output capture from SaveAudio
  - [ ] Test output capture from custom nodes
  - [ ] Test multipart building
  - [ ] Test webhook sending on task_done

---

## Phase 6: ComfyUI Nodes

### 6.1 WebhookReceiver Node
- [ ] Create `nodes/receiver.py`
  - [ ] Implement `WebhookReceiver` class
    - [ ] `INPUT_TYPES` with optional defaults
    - [ ] Hidden inputs: `PROMPT`, `EXTRA_PNGINFO`, `UNIQUE_ID`
    - [ ] `RETURN_TYPES = ("WEBHOOK_CONTEXT",)`
    - [ ] `FUNCTION = "receive"`
    - [ ] `CATEGORY = "webhook"`
  - [ ] Extract `webhook_config` from `extra_pnginfo`
  - [ ] Extract `webhook_inputs` from `extra_pnginfo`
  - [ ] Build `WebhookContext`
  - [ ] Call `register_webhook_context(context)`

### 6.2 WebhookInput Nodes - Text
- [ ] Create `nodes/inputs.py`
  - [ ] Implement `WebhookTextInput` class
    - [ ] Extract single string from context inputs
    - [ ] Support default value
  - [ ] Implement `WebhookTextsInput` class
    - [ ] Extract string array from context inputs
    - [ ] `OUTPUT_IS_LIST = (True,)`

### 6.3 WebhookInput Nodes - Numeric
- [ ] Implement `WebhookIntInput` class
  - [ ] Extract integer with default
  - [ ] Convert to int
- [ ] Implement `WebhookFloatInput` class
  - [ ] Extract float with default
  - [ ] Convert to float
- [ ] Implement `WebhookBoolInput` class
  - [ ] Extract boolean with default
  - [ ] Convert to bool

### 6.4 WebhookInput Nodes - Images
- [ ] Implement `WebhookImageInput` class
  - [ ] Extract single image (base64 or URL)
  - [ ] Return `IMAGE` tensor
  - [ ] Handle missing input (return empty tensor)
- [ ] Implement `WebhookImagesInput` class
  - [ ] Extract image array
  - [ ] Batch into single tensor [N, H, W, C]
  - [ ] Handle mixed base64/URL

### 6.5 WebhookInput Nodes - Media
- [ ] Implement `WebhookAudioInput` class
  - [ ] Extract audio (base64 or URL)
  - [ ] Return `AUDIO` dict
- [ ] Implement `WebhookVideoInput` class
  - [ ] Extract video (base64 or URL)
  - [ ] Return `VIDEO` type
- [ ] Implement `WebhookMaskInput` class
  - [ ] Extract mask image
  - [ ] Return `MASK` tensor

### 6.6 WebhookInput Nodes - Data
- [ ] Implement `WebhookJSONInput` class
  - [ ] Extract JSON dict, serialize to string

### 6.7 WebhookSend Node (Manual Output)
- [ ] Create `nodes/send.py`
  - [ ] Implement `WebhookSend` class
    - [ ] `OUTPUT_NODE = True`
    - [ ] Accept `WEBHOOK_CONTEXT` + optional images/audio/video/text/data
    - [ ] Process outputs and send via client
    - [ ] Return empty dict (output node)

### 6.8 Node Registration
- [ ] Update `__init__.py`
  - [ ] Import all node classes
  - [ ] Populate `NODE_CLASS_MAPPINGS` dict
  - [ ] Populate `NODE_DISPLAY_NAME_MAPPINGS` dict
  - [ ] Set `CATEGORY` for organization

### 6.9 Node Tests
- [ ] Create `tests/test_nodes.py`
  - [ ] Test WebhookReceiver extracts config
  - [ ] Test WebhookReceiver extracts inputs
  - [ ] Test WebhookTextInput extraction
  - [ ] Test WebhookTextsInput extraction (list)
  - [ ] Test WebhookIntInput extraction
  - [ ] Test WebhookFloatInput extraction
  - [ ] Test WebhookImageInput extraction
  - [ ] Test WebhookImagesInput batching
  - [ ] Test WebhookAudioInput extraction
  - [ ] Test WebhookMaskInput extraction
  - [ ] Test WebhookSend multipart output

---

## Phase 7: Event System

### 7.1 Event Payloads
- [ ] Create `core/events.py`
  - [ ] Implement `build_started_payload(context) -> dict`
  - [ ] Implement `build_progress_payload(context, node_id, node_type, progress, message) -> dict`
  - [ ] Implement `build_output_ready_payload(context, output_info) -> dict`
  - [ ] Implement `build_batch_payload(context, outputs, status) -> dict`
  - [ ] Implement `build_error_payload(context, error) -> dict`
  - [ ] Implement `build_completed_payload(context, stats) -> dict`

### 7.2 Progress Integration
- [ ] Hook into ComfyUI progress system
- [ ] Throttle progress updates (configurable interval_ms)
- [ ] Send progress events to webhook

### 7.3 Lifecycle Events
- [ ] Send `workflow.started` on execution begin
- [ ] Send `workflow.completed` on success
- [ ] Send `workflow.error` on failure
- [ ] Send `workflow.interrupted` on cancel

---

## Phase 8: Advanced Features

### 8.1 Circuit Breaker (Optional)
- [ ] Create `core/circuit_breaker.py`
  - [ ] Implement `CircuitState` enum (CLOSED, OPEN, HALF_OPEN)
  - [ ] Implement `CircuitBreaker` class
  - [ ] Per-URL circuit breakers
  - [ ] Failure threshold and recovery timeout

### 8.2 Delivery Queue (Optional)
- [ ] Create `core/delivery_queue.py`
  - [ ] Persistent queue for failed deliveries
  - [ ] Background retry task
  - [ ] Dead letter queue

### 8.3 Webhook Signature (Optional)
- [ ] Implement HMAC-SHA256 signature
- [ ] Add signature to `X-Webhook-Signature` header
- [ ] Document verification on receiver side

### 8.4 Metrics (Optional)
- [ ] Track request counts (success/failure)
- [ ] Track latency
- [ ] Track retry counts

---

## Phase 9: Testing

### 9.1 Mock Webhook Server
- [ ] Create `tests/mock_server.py`
  - [ ] Async test server (aiohttp)
  - [ ] Record received requests
  - [ ] Configurable response delays
  - [ ] Configurable error responses
  - [ ] Verify multipart structure

### 9.2 Unit Tests
- [ ] Test all input processors
- [ ] Test all output detectors
- [ ] Test HTTP client with mocked aiohttp
- [ ] Test payload builders
- [ ] Test interceptor logic
- [ ] Aim for >80% code coverage

### 9.3 Integration Tests
- [ ] Create `tests/test_integration.py`
  - [ ] Test full node graph execution
  - [ ] Test with mock webhook server
  - [ ] Test variable injection
  - [ ] Test multiple output nodes
  - [ ] Test custom node output capture

### 9.4 End-to-End Tests
- [ ] Create `tests/test_e2e.py`
  - [ ] Test via ComfyUI API
  - [ ] Submit workflow with webhook_config in extra_data
  - [ ] Verify all events received
  - [ ] Verify multipart payload structure
  - [ ] Verify file integrity

### 9.5 Failure Scenario Tests
- [ ] Test webhook endpoint timeout
- [ ] Test webhook endpoint 500 errors
- [ ] Test network disconnection
- [ ] Test invalid URL handling
- [ ] Test very large files
- [ ] Test recovery after failures

---

## Phase 10: Documentation

### 10.1 README.md
- [ ] Write project overview
- [ ] Add installation instructions
- [ ] Add quick start guide
- [ ] Add example webhook request
- [ ] Add example multipart response
- [ ] Add troubleshooting section

### 10.2 API Documentation
- [ ] Document webhook_config schema
- [ ] Document webhook_inputs schema
- [ ] Document all event types
- [ ] Document multipart payload structure
- [ ] Provide example payloads

### 10.3 Integration Guide
- [ ] Write guide for receiving webhooks
- [ ] Provide example receiver (Python/FastAPI)
- [ ] Provide example receiver (Node.js/Express)
- [ ] Document multipart parsing

### 10.4 Code Documentation
- [ ] Add docstrings to all public functions
- [ ] Add type hints throughout
- [ ] Add inline comments for complex logic

---

## Phase 11: Production Readiness

### 11.1 Error Handling Review
- [ ] Review all exception handling
- [ ] Ensure no unhandled exceptions crash ComfyUI
- [ ] Add graceful degradation
- [ ] Verify error messages are helpful

### 11.2 Security Review
- [ ] Review URL validation
- [ ] Review input sanitization
- [ ] Ensure no sensitive data in logs
- [ ] Review for injection vulnerabilities

### 11.3 Performance Review
- [ ] Profile memory usage for large batches
- [ ] Optimize streaming for large files
- [ ] Check for memory leaks
- [ ] Test concurrent workflows

### 11.4 Compatibility Testing
- [ ] Test with ComfyUI latest version
- [ ] Test on Windows
- [ ] Test on Linux
- [ ] Test on macOS
- [ ] Test with Python 3.10, 3.11, 3.12

### 11.5 Final Checklist
- [ ] All tests passing
- [ ] No critical security issues
- [ ] Documentation complete
- [ ] Examples working
- [ ] Error handling robust
- [ ] Logging appropriate

---

## Phase 12: Release

### 12.1 Packaging
- [ ] Finalize version number
- [ ] Update changelog
- [ ] Create release notes
- [ ] Tag release in git

### 12.2 Distribution
- [ ] Submit to ComfyUI Manager registry (optional)
- [ ] Create installation script if needed
- [ ] Test clean installation

### 12.3 Post-Release
- [ ] Monitor for issues
- [ ] Respond to bug reports
- [ ] Gather user feedback

---

## Priority Order

### P0 - Core (Must Have First)
1. Project structure setup (Phase 1)
2. Input processor core - text, int, float, bool (Phase 2.1, 2.7)
3. Output detection - images, audio (Phase 3.1)
4. HTTP client - multipart (Phase 4)
5. Output interceptor (Phase 5)
6. WebhookReceiver node (Phase 6.1)
7. Basic input nodes - text, int, float (Phase 6.2, 6.3)

### P1 - Essential
1. Image input processing (Phase 2.2, 2.3)
2. Audio input processing (Phase 2.4)
3. WebhookImageInput node (Phase 6.4)
4. WebhookAudioInput node (Phase 6.5)
5. Progress events (Phase 7)
6. Unit tests (Phase 9.2)

### P2 - Important
1. Video input processing (Phase 2.5)
2. Mask input processing (Phase 2.6)
3. All output types detection (Phase 3)
4. WebhookSend manual node (Phase 6.7)
5. Integration tests (Phase 9.3)
6. Documentation (Phase 10)

### P3 - Nice to Have
1. Streaming multipart for large files (Phase 4.5)
2. Circuit breaker (Phase 8.1)
3. Delivery queue (Phase 8.2)
4. Webhook signatures (Phase 8.3)
5. Metrics (Phase 8.4)

---

## Notes

- Start with P0 items to get a working prototype
- Test frequently with real ComfyUI workflows
- The interceptor is the key to universal output support
- Keep multipart as the only output format for simplicity
- Prioritize reliability over features
