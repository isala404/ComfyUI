"""Tests for validation utilities."""

import pytest

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.validation import (
    validate_url,
    sanitize_for_logging,
    is_base64_data,
    is_url,
    is_data_url,
    parse_data_url,
)


class TestValidateUrl:
    """Tests for validate_url function."""

    def test_valid_http_url(self):
        """Test valid HTTP URL."""
        valid, error = validate_url("http://example.com/webhook")
        assert valid is True
        assert error is None

    def test_valid_https_url(self):
        """Test valid HTTPS URL."""
        valid, error = validate_url("https://example.com/webhook")
        assert valid is True
        assert error is None

    def test_empty_url(self):
        """Test empty URL."""
        valid, error = validate_url("")
        assert valid is False
        assert "empty" in error.lower()

    def test_invalid_scheme(self):
        """Test invalid URL scheme."""
        valid, error = validate_url("ftp://example.com")
        assert valid is False
        assert "scheme" in error.lower()

    def test_require_https(self):
        """Test HTTPS requirement."""
        valid, error = validate_url("http://example.com", require_https=True)
        assert valid is False
        assert "https" in error.lower()

        valid, error = validate_url("https://example.com", require_https=True)
        assert valid is True

    def test_block_localhost(self):
        """Test blocking localhost."""
        valid, error = validate_url(
            "http://localhost/webhook",
            block_private_ips=True
        )
        assert valid is False
        assert "localhost" in error.lower()

    def test_block_private_ip(self):
        """Test blocking private IPs."""
        valid, error = validate_url(
            "http://192.168.1.1/webhook",
            block_private_ips=True
        )
        assert valid is False
        assert "private" in error.lower()


class TestSanitizeForLogging:
    """Tests for sanitize_for_logging function."""

    def test_redact_sensitive_keys(self):
        """Test redaction of sensitive keys."""
        data = {
            "callback_url": "https://example.com",
            "auth_value": "secret-token",
            "api_key": "my-api-key",
        }
        sanitized = sanitize_for_logging(data)

        assert sanitized["callback_url"] == "https://example.com"
        assert sanitized["auth_value"] == "[REDACTED]"
        assert sanitized["api_key"] == "[REDACTED]"

    def test_nested_redaction(self):
        """Test redaction in nested dictionaries."""
        data = {
            "config": {
                "url": "https://example.com",
                "password": "secret",
            }
        }
        sanitized = sanitize_for_logging(data)
        assert sanitized["config"]["password"] == "[REDACTED]"

    def test_long_base64_truncated(self):
        """Test long base64 strings are truncated."""
        data = {
            "image": "A" * 200,  # Long string
        }
        sanitized = sanitize_for_logging(data)
        assert "[BASE64_DATA:" in sanitized["image"]


class TestIsBase64Data:
    """Tests for is_base64_data function."""

    def test_data_url(self):
        """Test data URL detection."""
        assert is_base64_data("data:image/png;base64,ABC123") is True

    def test_raw_base64(self):
        """Test raw base64 detection."""
        # Long base64-like string
        long_b64 = "A" * 100 + "=="
        assert is_base64_data(long_b64) is True

    def test_short_string(self):
        """Test short string is not detected as base64."""
        assert is_base64_data("hello") is False


class TestIsUrl:
    """Tests for is_url function."""

    def test_http_url(self):
        """Test HTTP URL detection."""
        assert is_url("http://example.com") is True

    def test_https_url(self):
        """Test HTTPS URL detection."""
        assert is_url("https://example.com") is True

    def test_not_url(self):
        """Test non-URL strings."""
        assert is_url("not a url") is False
        assert is_url("ftp://example.com") is False


class TestIsDataUrl:
    """Tests for is_data_url function."""

    def test_valid_data_url(self):
        """Test valid data URL detection."""
        assert is_data_url("data:image/png;base64,ABC") is True
        assert is_data_url("data:text/plain,hello") is True

    def test_not_data_url(self):
        """Test non-data URL strings."""
        assert is_data_url("https://example.com") is False
        assert is_data_url("just text") is False


class TestParseDataUrl:
    """Tests for parse_data_url function."""

    def test_parse_base64_image(self):
        """Test parsing base64 image data URL."""
        import base64
        original = b"test data"
        b64 = base64.b64encode(original).decode()
        data_url = f"data:image/png;base64,{b64}"

        mime_type, decoded = parse_data_url(data_url)
        assert mime_type == "image/png"
        assert decoded == original

    def test_parse_text_data_url(self):
        """Test parsing text data URL."""
        data_url = "data:text/plain,hello%20world"
        mime_type, decoded = parse_data_url(data_url)
        assert mime_type == "text/plain"
        assert decoded == b"hello world"

    def test_invalid_data_url(self):
        """Test parsing invalid data URL."""
        mime_type, decoded = parse_data_url("not a data url")
        assert mime_type is None
        assert decoded is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
