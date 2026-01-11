"""Core data types for webhook functionality."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional
from datetime import datetime
import uuid


class WebhookEvent(Enum):
    """Types of webhook events."""
    STARTED = "workflow.started"
    PROGRESS = "workflow.progress"
    OUTPUT_READY = "output.ready"
    OUTPUT_BATCH = "output.batch"
    COMPLETED = "workflow.completed"
    ERROR = "workflow.error"
    INTERRUPTED = "workflow.interrupted"


@dataclass
class WebhookContext:
    """
    Context object containing webhook configuration and inputs.
    Created by WebhookReceiver and passed through the workflow.
    """
    callback_url: str
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    auth_header: Optional[str] = None
    auth_value: Optional[str] = None
    send_progress: bool = True
    progress_interval_ms: int = 1000
    timeout: int = 60
    max_retries: int = 3
    inputs: dict = field(default_factory=dict)
    prompt_id: Optional[str] = None
    include_workflow_in_response: bool = False
    start_time: Optional[datetime] = None

    def __post_init__(self):
        """Initialize start time when context is created."""
        if self.start_time is None:
            self.start_time = datetime.now()

    def get_auth_headers(self) -> dict:
        """Get authentication headers if configured."""
        if self.auth_header and self.auth_value:
            return {self.auth_header: self.auth_value}
        return {}

    def get_input(self, name: str, default: Any = None) -> Any:
        """Get an input value by name with optional default."""
        return self.inputs.get(name, default)


@dataclass
class WebhookResult:
    """Result of a webhook HTTP request."""
    success: bool
    status: Optional[int] = None
    error: Optional[str] = None
    response_body: Optional[str] = None
    elapsed_ms: float = 0.0
    retries: int = 0


@dataclass
class OutputInfo:
    """
    Information about a single output file or inline content.
    Used for building multipart payloads.
    """
    type: str  # image, audio, video, mesh, text, latent, unknown
    filename: Optional[str] = None
    subfolder: Optional[str] = None
    folder_type: Optional[str] = None  # output, temp, input
    mime_type: str = "application/octet-stream"
    inline_content: Optional[str] = None
    file_data: Optional[bytes] = None
    file_size_bytes: Optional[int] = None

    # Additional metadata
    width: Optional[int] = None
    height: Optional[int] = None
    sample_rate: Optional[int] = None
    duration_seconds: Optional[float] = None
    format: Optional[str] = None
    node_id: Optional[str] = None
    node_type: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        result = {"type": self.type}

        if self.filename:
            result["filename"] = self.filename
        if self.subfolder:
            result["subfolder"] = self.subfolder
        if self.format:
            result["format"] = self.format
        if self.file_size_bytes is not None:
            result["file_size_bytes"] = self.file_size_bytes
        if self.width is not None:
            result["width"] = self.width
        if self.height is not None:
            result["height"] = self.height
        if self.sample_rate is not None:
            result["sample_rate"] = self.sample_rate
        if self.duration_seconds is not None:
            result["duration_seconds"] = self.duration_seconds
        if self.node_id:
            result["node_id"] = self.node_id
        if self.node_type:
            result["node_type"] = self.node_type
        if self.inline_content is not None:
            result["content"] = self.inline_content

        return result
