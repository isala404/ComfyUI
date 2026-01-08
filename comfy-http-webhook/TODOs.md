# ComfyUI HTTP Webhook Node - Implementation Checklist

This document provides a comprehensive, prioritized checklist for implementing the HTTP webhook node system from zero to production.

---

## Phase 1: Project Setup & Foundation

### 1.1 Project Structure
- [ ] Create `custom_nodes/comfy-http-webhook/` directory
- [ ] Create `__init__.py` with `NODE_CLASS_MAPPINGS` and `NODE_DISPLAY_NAME_MAPPINGS`
- [ ] Create `requirements.txt` with dependencies
- [ ] Create `.gitignore` for Python projects
- [ ] Create `README.md` with basic documentation
- [ ] Set up `pyproject.toml` for proper packaging (optional)

### 1.2 Core Types & Data Structures
- [ ] Create `core/types.py`
  - [ ] Define `WebhookConfig` dataclass
  - [ ] Define `WebhookResult` dataclass
  - [ ] Define `OutputData` dataclass
  - [ ] Define `WebhookEvent` enum (started, progress, output, completed, error)
  - [ ] Define `OutputType` enum (image, audio, video, mesh, generic)
  - [ ] Define `EncodingType` enum (base64, url, multipart)

### 1.3 Utility Functions
- [ ] Create `utils/validation.py`
  - [ ] Implement `validate_url(url: str) -> bool`
  - [ ] Implement `validate_json_string(s: str) -> dict`
  - [ ] Implement `sanitize_for_logging(data: dict) -> dict`
  - [ ] Add URL scheme validation (http/https only)
  - [ ] Add optional private IP blocking
- [ ] Create `utils/encoding.py`
  - [ ] Implement `to_base64(data: bytes) -> str`
  - [ ] Implement `from_base64(s: str) -> bytes`
  - [ ] Implement `generate_request_id() -> str`
  - [ ] Implement `get_iso_timestamp() -> str`
- [ ] Create `utils/logging.py`
  - [ ] Set up structured logging for webhook operations
  - [ ] Implement log rotation (if needed)
  - [ ] Add debug mode toggle

---

## Phase 2: HTTP Client Implementation

### 2.1 Core Client
- [ ] Create `core/client.py`
  - [ ] Implement `WebhookClient` class
    - [ ] `__init__` with configuration parameters
    - [ ] `async get_session() -> aiohttp.ClientSession` (lazy initialization)
    - [ ] `async close()` for cleanup
    - [ ] `async send_webhook(url, payload, headers) -> WebhookResult`
    - [ ] `async send_multipart(url, payload, files, headers) -> WebhookResult`

### 2.2 Retry Logic
- [ ] Implement exponential backoff in `client.py`
  - [ ] `_calculate_delay(attempt: int) -> float` with jitter
  - [ ] `async _execute_with_retry(request_func) -> WebhookResult`
  - [ ] Define retryable status codes (408, 429, 500, 502, 503, 504)
  - [ ] Define non-retryable status codes (400, 401, 403, 404, 422)
  - [ ] Handle `aiohttp.ClientError` exceptions
  - [ ] Handle `asyncio.TimeoutError`
  - [ ] Log retry attempts with timing info

### 2.3 Circuit Breaker
- [ ] Create `core/circuit_breaker.py`
  - [ ] Implement `CircuitState` enum (CLOSED, OPEN, HALF_OPEN)
  - [ ] Implement `CircuitBreaker` class
    - [ ] `__init__` with failure threshold and recovery timeout
    - [ ] `can_execute() -> bool`
    - [ ] `record_success()`
    - [ ] `record_failure()`
    - [ ] `_check_recovery()` for state transitions
  - [ ] Add per-URL circuit breakers
  - [ ] Add circuit breaker metrics/stats

### 2.4 Client Tests
- [ ] Create `tests/test_client.py`
  - [ ] Test successful webhook delivery
  - [ ] Test retry on server errors (500, 502, 503)
  - [ ] Test no retry on client errors (400, 404)
  - [ ] Test exponential backoff timing
  - [ ] Test jitter randomization
  - [ ] Test timeout handling
  - [ ] Test connection error handling
  - [ ] Test circuit breaker activation
  - [ ] Test circuit breaker recovery
  - [ ] Test session reuse

---

## Phase 3: Payload Building

### 3.1 Payload Builders
- [ ] Create `core/payloads.py`
  - [ ] Implement `build_base_payload(event, request_id, prompt_id) -> dict`
  - [ ] Implement `build_started_payload(config, prompt_id) -> dict`
  - [ ] Implement `build_progress_payload(config, prompt_id, progress_info) -> dict`
  - [ ] Implement `build_output_payload(config, prompt_id, output_data) -> dict`
  - [ ] Implement `build_completed_payload(config, prompt_id, stats) -> dict`
  - [ ] Implement `build_error_payload(config, prompt_id, error_info) -> dict`
  - [ ] Implement `build_interrupted_payload(config, prompt_id, partial_results) -> dict`

### 3.2 Payload Validation
- [ ] Add payload size checking
- [ ] Add payload schema validation (optional, with pydantic)
- [ ] Add compression for large payloads (optional)

### 3.3 Payload Tests
- [ ] Create `tests/test_payloads.py`
  - [ ] Test all payload builders produce valid JSON
  - [ ] Test required fields are present
  - [ ] Test timestamp format is ISO8601
  - [ ] Test payload size limits

---

## Phase 4: Output Processors

### 4.1 Image Processor
- [ ] Create `processors/image.py`
  - [ ] Implement `process_image(tensor, format, quality) -> bytes`
  - [ ] Support PNG format (lossless)
  - [ ] Support JPEG format (lossy with quality setting)
  - [ ] Support WebP format (modern, configurable)
  - [ ] Handle batch images (multiple tensors)
  - [ ] Extract image dimensions
  - [ ] Handle different tensor formats (BCHW, BHWC)
  - [ ] Implement metadata embedding for PNG
  - [ ] Implement `ImageOutputData` dataclass

### 4.2 Audio Processor
- [ ] Create `processors/audio.py`
  - [ ] Implement `process_audio(audio_dict, format) -> bytes`
  - [ ] Support FLAC format (lossless)
  - [ ] Support MP3 format (with quality options)
  - [ ] Support Opus format (efficient)
  - [ ] Support WAV format (uncompressed)
  - [ ] Extract sample rate, channels, duration
  - [ ] Handle stereo/mono conversion if needed
  - [ ] Implement `AudioOutputData` dataclass

### 4.3 Video Processor
- [ ] Create `processors/video.py`
  - [ ] Implement `process_video(frames, format, fps) -> bytes`
  - [ ] Support WebM format (VP9 codec)
  - [ ] Support MP4 format (H.264 codec) - optional, requires additional libs
  - [ ] Handle frame tensor conversion
  - [ ] Calculate duration from frame count and fps
  - [ ] Implement `VideoOutputData` dataclass
  - [ ] Add progress callback for long videos

### 4.4 Mesh Processor
- [ ] Create `processors/mesh.py`
  - [ ] Implement `process_mesh(mesh_data, format) -> bytes`
  - [ ] Support GLB format (binary glTF)
  - [ ] Support OBJ format (optional)
  - [ ] Extract vertex/face counts
  - [ ] Handle texture data if present
  - [ ] Implement `MeshOutputData` dataclass

### 4.5 Generic Processor
- [ ] Create `processors/generic.py`
  - [ ] Implement `process_generic(data, output_name) -> dict`
  - [ ] Handle JSON-serializable types
  - [ ] Handle torch tensors (convert to lists)
  - [ ] Handle numpy arrays
  - [ ] Add type detection and appropriate serialization

### 4.6 Processor Tests
- [ ] Create `tests/test_processors.py`
  - [ ] Test image processing for all formats
  - [ ] Test audio processing for all formats
  - [ ] Test video processing
  - [ ] Test mesh processing
  - [ ] Test generic data serialization
  - [ ] Test batch handling
  - [ ] Test error handling for invalid inputs

---

## Phase 5: ComfyUI Nodes

### 5.1 WebhookConfig Node
- [ ] Create `nodes/config_node.py`
  - [ ] Implement `WebhookConfig` class
    - [ ] Define `INPUT_TYPES` with all config options
    - [ ] Define `RETURN_TYPES = ("WEBHOOK_CONFIG",)`
    - [ ] Define `FUNCTION = "create_config"`
    - [ ] Define `CATEGORY = "webhook"`
    - [ ] Implement `create_config()` method
  - [ ] Validate callback_url on creation
  - [ ] Generate request_id if not provided
  - [ ] Parse custom_metadata JSON
  - [ ] Store config in execution context for access by output nodes

### 5.2 WebhookVariable Nodes
- [ ] Create `nodes/variable_nodes.py`
  - [ ] Implement `WebhookStringVariable` class
    - [ ] Access `extra_data.webhook_variables` via hidden PROMPT input
    - [ ] Return default_value if variable not found
  - [ ] Implement `WebhookIntVariable` class
    - [ ] Add min/max validation
  - [ ] Implement `WebhookFloatVariable` class
    - [ ] Add min/max/step validation
  - [ ] Implement `WebhookBooleanVariable` class
  - [ ] Implement `WebhookImageVariable` class
    - [ ] Handle base64 image input
    - [ ] Handle URL image input (download)
    - [ ] Convert to IMAGE tensor
  - [ ] Implement `WebhookSeedVariable` class
    - [ ] Handle -1 for random seed

### 5.3 WebhookOutput Nodes
- [ ] Create `nodes/output_nodes.py`
  - [ ] Implement `WebhookImageOutput` class
    - [ ] Define `OUTPUT_NODE = True`
    - [ ] Accept IMAGE and WEBHOOK_CONFIG inputs
    - [ ] Process images using image processor
    - [ ] Send to webhook endpoint
    - [ ] Also save locally (standard behavior)
    - [ ] Return UI data for frontend
  - [ ] Implement `WebhookAudioOutput` class
    - [ ] Same pattern as image output
  - [ ] Implement `WebhookVideoOutput` class
    - [ ] Handle frame sequences
    - [ ] Handle VIDEO type if available
  - [ ] Implement `WebhookMeshOutput` class
    - [ ] Handle MESH type
  - [ ] Implement `WebhookGenericOutput` class
    - [ ] Handle ANY type

### 5.4 WebhookProgress Node (Optional)
- [ ] Create `nodes/progress_node.py`
  - [ ] Implement `WebhookProgressUpdate` class
    - [ ] Send custom progress message
    - [ ] Pass through input for execution order
    - [ ] Non-blocking async send

### 5.5 Node Registration
- [ ] Update `__init__.py`
  - [ ] Import all node classes
  - [ ] Populate `NODE_CLASS_MAPPINGS`
  - [ ] Populate `NODE_DISPLAY_NAME_MAPPINGS`
  - [ ] Add `WEB_DIRECTORY` if frontend components needed

### 5.6 Node Tests
- [ ] Create `tests/test_nodes.py`
  - [ ] Test WebhookConfig creates valid config
  - [ ] Test WebhookVariable nodes extract values
  - [ ] Test WebhookVariable nodes use defaults
  - [ ] Test WebhookOutput nodes process outputs
  - [ ] Test WebhookOutput nodes call webhook
  - [ ] Test node integration (config → output)

---

## Phase 6: Execution Integration

### 6.1 Output Coordinator
- [ ] Create `core/coordinator.py`
  - [ ] Implement `OutputCoordinator` class
    - [ ] Track total expected outputs
    - [ ] Track completed outputs
    - [ ] Store output results
    - [ ] Send completion event when all done
    - [ ] Handle partial completion (interruption)
  - [ ] Implement coordinator registry (per prompt_id)
  - [ ] Add cleanup for completed/failed workflows

### 6.2 Progress Integration
- [ ] Hook into ComfyUI progress system
  - [ ] Create custom progress handler for webhooks
  - [ ] Implement progress throttling (configurable interval)
  - [ ] Forward progress updates to webhook
  - [ ] Include node info in progress updates

### 6.3 Error Handling Integration
- [ ] Create `core/error_handler.py`
  - [ ] Implement `WebhookErrorHandler` class
  - [ ] Hook into execution error events
  - [ ] Format error info for webhook
  - [ ] Send error event on execution failure
  - [ ] Continue local execution even if webhook fails

### 6.4 Lifecycle Events
- [ ] Implement workflow started event
  - [ ] Hook into execution start
  - [ ] Send started event with workflow info
- [ ] Implement workflow completed event
  - [ ] Track execution time
  - [ ] Aggregate output statistics
  - [ ] Send completed event
- [ ] Implement workflow interrupted event
  - [ ] Hook into interrupt signal
  - [ ] Send interrupted event with partial results

---

## Phase 7: Advanced Features

### 7.1 Delivery Queue (For Failed Webhooks)
- [ ] Create `core/delivery_queue.py`
  - [ ] Implement persistent queue (file-based or SQLite)
  - [ ] Store failed webhook deliveries
  - [ ] Background retry task
  - [ ] Maximum retry limit
  - [ ] Dead letter queue for permanent failures
  - [ ] Queue statistics/monitoring

### 7.2 Request Batching
- [ ] Implement output batching for efficiency
  - [ ] Collect multiple outputs
  - [ ] Send as single batch request
  - [ ] Configurable batch size/timeout
  - [ ] Fall back to individual sends on failure

### 7.3 Streaming Support (Optional)
- [ ] Implement chunked transfer for large files
  - [ ] Split large payloads into chunks
  - [ ] Send with proper headers
  - [ ] Handle reassembly on receiver side

### 7.4 Webhook Signature
- [ ] Implement HMAC signature for webhook verification
  - [ ] Add secret key to config
  - [ ] Sign payloads with SHA-256
  - [ ] Add signature to headers
  - [ ] Document verification on receiver side

### 7.5 Metrics & Monitoring
- [ ] Add metrics collection
  - [ ] Request count (success/failure)
  - [ ] Request latency
  - [ ] Retry count
  - [ ] Circuit breaker state changes
  - [ ] Queue depth
- [ ] Expose metrics endpoint (optional)
- [ ] Add logging for all webhook operations

---

## Phase 8: Testing

### 8.1 Mock Webhook Server
- [ ] Create `tests/mock_server.py`
  - [ ] Implement async test server
  - [ ] Record received requests
  - [ ] Configurable response delays
  - [ ] Configurable error responses
  - [ ] Support for all event types

### 8.2 Unit Tests
- [ ] Test all utility functions
- [ ] Test all processors
- [ ] Test client with mocked aiohttp
- [ ] Test circuit breaker state machine
- [ ] Test payload builders
- [ ] Test coordinator logic
- [ ] Aim for >80% code coverage

### 8.3 Integration Tests
- [ ] Create `tests/test_integration.py`
  - [ ] Test full node graph execution
  - [ ] Test with mock webhook server
  - [ ] Test variable injection
  - [ ] Test multiple output nodes
  - [ ] Test error scenarios

### 8.4 End-to-End Tests
- [ ] Create `tests/test_e2e.py`
  - [ ] Test via ComfyUI API
  - [ ] Submit workflow with webhook config
  - [ ] Verify all events received
  - [ ] Verify payload structure
  - [ ] Verify output data integrity

### 8.5 Performance Tests
- [ ] Create `tests/test_performance.py`
  - [ ] Test concurrent workflows
  - [ ] Test large image batches
  - [ ] Test rapid progress updates
  - [ ] Test memory usage
  - [ ] Establish performance baselines

### 8.6 Failure Scenario Tests
- [ ] Test webhook endpoint timeout
- [ ] Test webhook endpoint errors (500)
- [ ] Test network disconnection
- [ ] Test invalid URL handling
- [ ] Test malformed payload handling
- [ ] Test circuit breaker activation
- [ ] Test recovery after failures

---

## Phase 9: Documentation

### 9.1 README.md
- [ ] Write project overview
- [ ] Add installation instructions
- [ ] Add quick start guide
- [ ] Add configuration reference
- [ ] Add example workflows
- [ ] Add troubleshooting section
- [ ] Add FAQ

### 9.2 API Documentation
- [ ] Document webhook event types
- [ ] Document payload schemas
- [ ] Document all node inputs/outputs
- [ ] Provide example payloads for each event
- [ ] Document authentication options

### 9.3 Integration Guide
- [ ] Write guide for receiving webhooks
- [ ] Provide example receiver implementations
  - [ ] Python (Flask/FastAPI)
  - [ ] Node.js (Express)
  - [ ] Go
- [ ] Document webhook verification
- [ ] Document retry handling on receiver side

### 9.4 Code Documentation
- [ ] Add docstrings to all public functions
- [ ] Add type hints throughout
- [ ] Add inline comments for complex logic
- [ ] Generate API docs (optional, with Sphinx)

---

## Phase 10: Production Readiness

### 10.1 Error Handling Review
- [ ] Review all exception handling
- [ ] Ensure no unhandled exceptions crash ComfyUI
- [ ] Add graceful degradation everywhere
- [ ] Verify error messages are helpful

### 10.2 Security Review
- [ ] Review URL validation
- [ ] Review input sanitization
- [ ] Ensure no sensitive data in logs
- [ ] Review authentication handling
- [ ] Add rate limiting if needed
- [ ] Review for injection vulnerabilities

### 10.3 Performance Review
- [ ] Profile memory usage
- [ ] Optimize large payload handling
- [ ] Review async patterns for efficiency
- [ ] Check for memory leaks
- [ ] Optimize image encoding performance

### 10.4 Compatibility Testing
- [ ] Test with ComfyUI latest version
- [ ] Test with ComfyUI older versions (if supporting)
- [ ] Test on Windows
- [ ] Test on Linux
- [ ] Test on macOS
- [ ] Test with Python 3.10
- [ ] Test with Python 3.11
- [ ] Test with Python 3.12

### 10.5 Final Checklist
- [ ] All tests passing
- [ ] No critical security issues
- [ ] Documentation complete
- [ ] Examples working
- [ ] Performance acceptable
- [ ] Error handling robust
- [ ] Logging appropriate
- [ ] Code clean and maintainable

---

## Phase 11: Release

### 11.1 Packaging
- [ ] Finalize version number
- [ ] Update changelog
- [ ] Create release notes
- [ ] Tag release in git
- [ ] Create GitHub release

### 11.2 Distribution
- [ ] Submit to ComfyUI Manager registry (optional)
- [ ] Create installation script if needed
- [ ] Test clean installation

### 11.3 Post-Release
- [ ] Monitor for issues
- [ ] Respond to bug reports
- [ ] Plan future improvements
- [ ] Gather user feedback

---

## Priority Order

### P0 - Core Functionality (Must Have)
1. Project structure setup
2. HTTP client with retry logic
3. WebhookConfig node
4. WebhookImageOutput node
5. Basic payload building
6. Error handling

### P1 - Essential Features
1. Variable nodes (String, Int, Float)
2. Progress updates
3. Completion events
4. Audio output support
5. Unit tests for core

### P2 - Important Features
1. Circuit breaker
2. Video output support
3. 3D mesh output support
4. Integration tests
5. Documentation

### P3 - Nice to Have
1. Delivery queue
2. Request batching
3. Webhook signatures
4. Metrics/monitoring
5. Performance optimizations

---

## Time Estimates (Rough)

| Phase | Estimated Time |
|-------|---------------|
| Phase 1: Setup | 2-4 hours |
| Phase 2: HTTP Client | 4-6 hours |
| Phase 3: Payloads | 2-3 hours |
| Phase 4: Processors | 6-8 hours |
| Phase 5: Nodes | 6-8 hours |
| Phase 6: Integration | 4-6 hours |
| Phase 7: Advanced | 8-12 hours |
| Phase 8: Testing | 8-12 hours |
| Phase 9: Documentation | 4-6 hours |
| Phase 10: Production | 4-6 hours |
| Phase 11: Release | 2-4 hours |

**Total: ~50-75 hours** for a complete, production-ready implementation.

---

## Notes

- Start with P0 items to get a working prototype
- Iterate based on testing and feedback
- Don't over-engineer early - add complexity as needed
- Keep the core simple and extensible
- Prioritize reliability over features
