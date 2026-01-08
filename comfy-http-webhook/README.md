# ComfyUI HTTP Webhook Node

A production-quality custom node package for ComfyUI that enables HTTP webhook integration for triggering workflows and receiving outputs.

## Features

- **Trigger workflows via HTTP** with dynamic variables
- **Real-time progress updates** sent to your webhook endpoint
- **Output delivery** for images, audio, video, and 3D meshes
- **Completion notifications** with status and metadata
- **Reliable delivery** with exponential backoff retry logic
- **Production-ready** with circuit breaker, error handling, and logging

## Status

**Currently in planning phase.** See:
- [PLAN.md](./PLAN.md) - Detailed architecture and design
- [TODOs.md](./TODOs.md) - Implementation checklist

## Quick Start

### Installation

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/your-repo/comfy-http-webhook.git
pip install -r comfy-http-webhook/requirements.txt
```

### Basic Usage

1. Add a **Webhook Config** node to your workflow
2. Configure your callback URL and authentication
3. Connect **Webhook Variable** nodes to inject dynamic inputs
4. Replace output nodes with **Webhook Output** nodes
5. Trigger your workflow via the ComfyUI API with webhook variables

### Example API Request

```json
{
  "prompt": { /* your workflow */ },
  "extra_data": {
    "webhook_variables": {
      "prompt_text": "a beautiful sunset over mountains",
      "seed": 42,
      "width": 1024,
      "height": 1024
    }
  }
}
```

### Webhook Events

Your endpoint will receive:

1. **workflow.started** - When execution begins
2. **workflow.progress** - During execution (configurable)
3. **output.ready** - For each output (image, audio, etc.)
4. **workflow.completed** - When all outputs are sent
5. **workflow.error** - If execution fails

## Documentation

- [Architecture & Design](./PLAN.md)
- [Implementation Checklist](./TODOs.md)

## Contributing

Contributions welcome! Please see the TODOs.md for areas that need work.

## License

MIT License - see LICENSE file for details.
