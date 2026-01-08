"""Tests for HTTP client."""

import pytest
import asyncio
import json

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.client import WebhookClient, get_webhook_client


class TestWebhookClient:
    """Tests for WebhookClient class."""

    def test_singleton(self):
        """Test singleton client access."""
        client1 = get_webhook_client()
        client2 = get_webhook_client()
        assert client1 is client2

    def test_init_defaults(self):
        """Test default initialization values."""
        client = WebhookClient()
        assert client.max_retries == 3
        assert client.base_delay == 1.0
        assert client.max_delay == 60.0

    def test_custom_init(self):
        """Test custom initialization values."""
        client = WebhookClient(
            timeout=30.0,
            max_retries=5,
            base_delay=0.5,
        )
        assert client.max_retries == 5
        assert client.base_delay == 0.5

    def test_calculate_delay(self):
        """Test exponential backoff calculation."""
        client = WebhookClient(base_delay=1.0, jitter_factor=0.0)

        # Without jitter, delays should follow 2^n pattern
        delay1 = client._calculate_delay(1)
        delay2 = client._calculate_delay(2)
        delay3 = client._calculate_delay(3)

        assert delay1 == pytest.approx(1.0, abs=0.1)
        assert delay2 == pytest.approx(2.0, abs=0.1)
        assert delay3 == pytest.approx(4.0, abs=0.1)

    def test_calculate_delay_max_cap(self):
        """Test delay is capped at max_delay."""
        client = WebhookClient(base_delay=1.0, max_delay=5.0, jitter_factor=0.0)

        # High attempt should be capped
        delay = client._calculate_delay(10)
        assert delay <= 5.0

    def test_retryable_status_codes(self):
        """Test retryable status codes."""
        assert 408 in WebhookClient.RETRYABLE_STATUS_CODES
        assert 429 in WebhookClient.RETRYABLE_STATUS_CODES
        assert 500 in WebhookClient.RETRYABLE_STATUS_CODES
        assert 502 in WebhookClient.RETRYABLE_STATUS_CODES
        assert 503 in WebhookClient.RETRYABLE_STATUS_CODES
        assert 504 in WebhookClient.RETRYABLE_STATUS_CODES

        # 4xx errors should not be retryable (except 408, 429)
        assert 400 not in WebhookClient.RETRYABLE_STATUS_CODES
        assert 401 not in WebhookClient.RETRYABLE_STATUS_CODES
        assert 403 not in WebhookClient.RETRYABLE_STATUS_CODES
        assert 404 not in WebhookClient.RETRYABLE_STATUS_CODES


class TestWebhookClientAsync:
    """Async tests for WebhookClient."""

    @pytest.fixture
    def client(self):
        """Create a client for testing."""
        return WebhookClient(timeout=5.0, max_retries=1)

    @pytest.mark.asyncio
    async def test_get_session(self, client):
        """Test session creation."""
        session = await client.get_session()
        assert session is not None
        assert not session.closed

        # Getting session again should return same instance
        session2 = await client.get_session()
        assert session is session2

        await client.close()

    @pytest.mark.asyncio
    async def test_close(self, client):
        """Test session closing."""
        # Create session
        session = await client.get_session()
        assert not session.closed

        # Close
        await client.close()
        assert client._session is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
