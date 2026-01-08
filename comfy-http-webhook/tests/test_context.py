"""Tests for context management."""

import pytest

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.types import WebhookContext
from core.context import (
    register_webhook_context,
    get_webhook_context,
    unregister_webhook_context,
    get_all_contexts,
    clear_all_contexts,
)


class TestContextRegistry:
    """Tests for context registry functions."""

    def setup_method(self):
        """Clear registry before each test."""
        clear_all_contexts()

    def teardown_method(self):
        """Clear registry after each test."""
        clear_all_contexts()

    def test_register_and_get(self):
        """Test registering and retrieving a context."""
        ctx = WebhookContext(
            callback_url="https://example.com",
            prompt_id="prompt-123",
        )
        register_webhook_context(ctx)

        retrieved = get_webhook_context("prompt-123")
        assert retrieved is not None
        assert retrieved.callback_url == "https://example.com"
        assert retrieved.prompt_id == "prompt-123"

    def test_get_nonexistent(self):
        """Test getting a context that doesn't exist."""
        result = get_webhook_context("nonexistent")
        assert result is None

    def test_unregister(self):
        """Test unregistering a context."""
        ctx = WebhookContext(
            callback_url="https://example.com",
            prompt_id="prompt-456",
        )
        register_webhook_context(ctx)

        # Verify it exists
        assert get_webhook_context("prompt-456") is not None

        # Unregister
        removed = unregister_webhook_context("prompt-456")
        assert removed is not None
        assert removed.prompt_id == "prompt-456"

        # Verify it's gone
        assert get_webhook_context("prompt-456") is None

    def test_unregister_nonexistent(self):
        """Test unregistering a context that doesn't exist."""
        result = unregister_webhook_context("nonexistent")
        assert result is None

    def test_register_without_prompt_id(self):
        """Test that registration fails without prompt_id."""
        ctx = WebhookContext(
            callback_url="https://example.com",
            prompt_id=None,
        )
        register_webhook_context(ctx)
        # Should not crash, but context won't be registered
        assert len(get_all_contexts()) == 0

    def test_multiple_contexts(self):
        """Test registering multiple contexts."""
        ctx1 = WebhookContext(callback_url="https://example1.com", prompt_id="p1")
        ctx2 = WebhookContext(callback_url="https://example2.com", prompt_id="p2")
        ctx3 = WebhookContext(callback_url="https://example3.com", prompt_id="p3")

        register_webhook_context(ctx1)
        register_webhook_context(ctx2)
        register_webhook_context(ctx3)

        all_contexts = get_all_contexts()
        assert len(all_contexts) == 3
        assert "p1" in all_contexts
        assert "p2" in all_contexts
        assert "p3" in all_contexts

    def test_clear_all(self):
        """Test clearing all contexts."""
        ctx1 = WebhookContext(callback_url="https://example1.com", prompt_id="p1")
        ctx2 = WebhookContext(callback_url="https://example2.com", prompt_id="p2")

        register_webhook_context(ctx1)
        register_webhook_context(ctx2)

        count = clear_all_contexts()
        assert count == 2
        assert len(get_all_contexts()) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
