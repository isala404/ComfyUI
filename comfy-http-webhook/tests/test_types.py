"""Tests for core types."""

import pytest
from datetime import datetime

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.types import WebhookContext, WebhookResult, OutputInfo, WebhookEvent


class TestWebhookContext:
    """Tests for WebhookContext dataclass."""

    def test_basic_creation(self):
        """Test basic context creation."""
        ctx = WebhookContext(
            callback_url="https://example.com/webhook",
            request_id="test-123",
        )
        assert ctx.callback_url == "https://example.com/webhook"
        assert ctx.request_id == "test-123"
        assert ctx.send_progress is True
        assert ctx.timeout == 60
        assert ctx.max_retries == 3
        assert ctx.inputs == {}

    def test_auto_request_id(self):
        """Test that request_id is auto-generated if not provided."""
        ctx = WebhookContext(callback_url="https://example.com")
        assert ctx.request_id is not None
        assert len(ctx.request_id) > 0

    def test_start_time_auto_set(self):
        """Test that start_time is auto-set."""
        ctx = WebhookContext(callback_url="https://example.com")
        assert ctx.start_time is not None
        assert isinstance(ctx.start_time, datetime)

    def test_get_auth_headers(self):
        """Test auth header generation."""
        ctx = WebhookContext(
            callback_url="https://example.com",
            auth_header="Authorization",
            auth_value="Bearer token123",
        )
        headers = ctx.get_auth_headers()
        assert headers == {"Authorization": "Bearer token123"}

    def test_get_auth_headers_empty(self):
        """Test empty auth headers."""
        ctx = WebhookContext(callback_url="https://example.com")
        headers = ctx.get_auth_headers()
        assert headers == {}

    def test_get_input(self):
        """Test input retrieval."""
        ctx = WebhookContext(
            callback_url="https://example.com",
            inputs={"prompt": "hello", "seed": 42},
        )
        assert ctx.get_input("prompt") == "hello"
        assert ctx.get_input("seed") == 42
        assert ctx.get_input("missing") is None
        assert ctx.get_input("missing", "default") == "default"


class TestWebhookResult:
    """Tests for WebhookResult dataclass."""

    def test_success_result(self):
        """Test successful result."""
        result = WebhookResult(success=True, status=200)
        assert result.success is True
        assert result.status == 200
        assert result.error is None

    def test_error_result(self):
        """Test error result."""
        result = WebhookResult(
            success=False,
            status=500,
            error="Internal Server Error",
        )
        assert result.success is False
        assert result.status == 500
        assert result.error == "Internal Server Error"


class TestOutputInfo:
    """Tests for OutputInfo dataclass."""

    def test_basic_creation(self):
        """Test basic output info creation."""
        info = OutputInfo(
            type="image",
            filename="test.png",
            subfolder="output",
            folder_type="output",
            mime_type="image/png",
        )
        assert info.type == "image"
        assert info.filename == "test.png"
        assert info.mime_type == "image/png"

    def test_to_dict(self):
        """Test conversion to dictionary."""
        info = OutputInfo(
            type="image",
            filename="test.png",
            format="png",
            width=1024,
            height=768,
            node_id="5",
            node_type="SaveImage",
        )
        d = info.to_dict()
        assert d["type"] == "image"
        assert d["filename"] == "test.png"
        assert d["format"] == "png"
        assert d["width"] == 1024
        assert d["height"] == 768
        assert d["node_id"] == "5"
        assert d["node_type"] == "SaveImage"

    def test_to_dict_inline(self):
        """Test inline content in dictionary."""
        info = OutputInfo(
            type="text",
            inline_content="Hello world",
            mime_type="text/plain",
        )
        d = info.to_dict()
        assert d["type"] == "text"
        assert d["content"] == "Hello world"


class TestWebhookEvent:
    """Tests for WebhookEvent enum."""

    def test_event_values(self):
        """Test event enum values."""
        assert WebhookEvent.STARTED.value == "workflow.started"
        assert WebhookEvent.PROGRESS.value == "workflow.progress"
        assert WebhookEvent.OUTPUT_READY.value == "output.ready"
        assert WebhookEvent.OUTPUT_BATCH.value == "output.batch"
        assert WebhookEvent.COMPLETED.value == "workflow.completed"
        assert WebhookEvent.ERROR.value == "workflow.error"
        assert WebhookEvent.INTERRUPTED.value == "workflow.interrupted"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
