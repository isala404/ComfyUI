"""
Production-grade async HTTP client for webhook delivery.
Supports multipart/form-data for file uploads with retry logic.
"""

import asyncio
import json
import logging
import random
import time
from typing import Optional
from pathlib import Path

import aiohttp

from .types import WebhookResult

logger = logging.getLogger(__name__)

# Singleton client instance
_webhook_client: Optional["WebhookClient"] = None


def get_webhook_client() -> "WebhookClient":
    """Get or create the singleton webhook client instance."""
    global _webhook_client
    if _webhook_client is None:
        _webhook_client = WebhookClient()
    return _webhook_client


class WebhookClient:
    """
    Production-grade async HTTP client for multipart webhook delivery.

    Features:
    - Async HTTP with connection pooling
    - Multipart/form-data support for file uploads
    - Exponential backoff with jitter for retries
    - Configurable timeout and retry settings
    """

    # Status codes that should trigger retry
    RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}

    def __init__(
        self,
        timeout: float = 60.0,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        jitter_factor: float = 0.2,
        max_connections: int = 10,
        max_connections_per_host: int = 5,
    ):
        """
        Initialize the webhook client.

        Args:
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
            base_delay: Base delay for exponential backoff
            max_delay: Maximum delay between retries
            jitter_factor: Random jitter factor (0-1)
            max_connections: Maximum total connections
            max_connections_per_host: Maximum connections per host
        """
        self._session: Optional[aiohttp.ClientSession] = None
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.jitter_factor = jitter_factor
        self.max_connections = max_connections
        self.max_connections_per_host = max_connections_per_host

    async def get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session with connection pooling."""
        if self._session is None or self._session.closed:
            connector = aiohttp.TCPConnector(
                limit=self.max_connections,
                limit_per_host=self.max_connections_per_host,
                keepalive_timeout=30,
                enable_cleanup_closed=True,
            )
            self._session = aiohttp.ClientSession(
                connector=connector,
                timeout=self.timeout,
            )
        return self._session

    async def send_json(
        self,
        url: str,
        payload: dict,
        headers: Optional[dict] = None,
    ) -> WebhookResult:
        """
        Send JSON payload to webhook URL.

        Used for progress events, errors, and status updates.

        Args:
            url: Webhook URL
            payload: JSON-serializable dictionary
            headers: Optional additional headers (e.g., auth)

        Returns:
            WebhookResult with success status and details
        """
        session = await self.get_session()
        all_headers = {"Content-Type": "application/json"}
        if headers:
            all_headers.update(headers)

        async def make_request():
            return session.post(url, json=payload, headers=all_headers)

        return await self._execute_with_retry(make_request)

    async def send_multipart(
        self,
        url: str,
        metadata: dict,
        files: list[tuple[str, str, bytes, str]],
        headers: Optional[dict] = None,
    ) -> WebhookResult:
        """
        Send multipart/form-data request with files.

        Args:
            url: Webhook URL
            metadata: JSON metadata dictionary
            files: List of (field_name, filename, binary_data, mime_type)
            headers: Optional additional headers (e.g., auth)

        Returns:
            WebhookResult with success status and details
        """
        session = await self.get_session()

        async def make_request():
            # Build FormData for each request (cannot reuse)
            form = aiohttp.FormData()

            # Add metadata as JSON part
            form.add_field(
                "metadata",
                json.dumps(metadata),
                content_type="application/json",
            )

            # Add files
            for name, filename, data, content_type in files:
                form.add_field(
                    name,
                    data,
                    filename=filename,
                    content_type=content_type,
                )

            return session.post(url, data=form, headers=headers)

        return await self._execute_with_retry(make_request)

    async def send_multipart_streaming(
        self,
        url: str,
        metadata: dict,
        file_paths: list[tuple[str, str, str, str]],
        headers: Optional[dict] = None,
    ) -> WebhookResult:
        """
        Send multipart request with files streamed from disk.

        Use this for large files (>50MB) to avoid memory issues.

        Args:
            url: Webhook URL
            metadata: JSON metadata dictionary
            file_paths: List of (field_name, filename, file_path, mime_type)
            headers: Optional additional headers (e.g., auth)

        Returns:
            WebhookResult with success status and details
        """
        session = await self.get_session()

        async def make_request():
            # Build multipart writer for streaming
            writer = aiohttp.MultipartWriter("form-data")

            # Add metadata
            metadata_payload = aiohttp.payload.JsonPayload(metadata)
            metadata_payload.set_content_disposition("form-data", name="metadata")
            writer.append_payload(metadata_payload)

            # Add files (streamed from disk)
            for name, filename, path, content_type in file_paths:
                file_path = Path(path)
                if file_path.exists():
                    with open(file_path, "rb") as f:
                        file_data = f.read()
                    payload = aiohttp.payload.BytesPayload(
                        file_data,
                        content_type=content_type,
                    )
                    payload.set_content_disposition(
                        "form-data", name=name, filename=filename
                    )
                    writer.append_payload(payload)

            return session.post(url, data=writer, headers=headers)

        return await self._execute_with_retry(make_request)

    async def _execute_with_retry(self, request_func) -> WebhookResult:
        """
        Execute request with exponential backoff and jitter.

        Args:
            request_func: Async function that returns a context manager for the request

        Returns:
            WebhookResult with success status and details
        """
        last_error = None
        start_time = time.time()
        retries = 0

        for attempt in range(self.max_retries + 1):
            try:
                if attempt > 0:
                    delay = self._calculate_delay(attempt)
                    logger.info(
                        f"Webhook retry {attempt}/{self.max_retries} after {delay:.2f}s"
                    )
                    await asyncio.sleep(delay)
                    retries = attempt

                async with request_func() as response:
                    elapsed_ms = (time.time() - start_time) * 1000

                    if response.status < 400:
                        return WebhookResult(
                            success=True,
                            status=response.status,
                            elapsed_ms=elapsed_ms,
                            retries=retries,
                        )

                    # Check if retryable
                    if response.status in self.RETRYABLE_STATUS_CODES:
                        last_error = f"HTTP {response.status}"
                        logger.warning(
                            f"Webhook request failed with retryable status {response.status}"
                        )
                        continue

                    # Non-retryable error
                    body = await response.text()
                    return WebhookResult(
                        success=False,
                        status=response.status,
                        error=f"HTTP {response.status}: {body[:500]}",
                        elapsed_ms=elapsed_ms,
                        retries=retries,
                    )

            except aiohttp.ClientError as e:
                last_error = f"Client error: {str(e)}"
                logger.warning(f"Webhook client error: {e}")
                continue
            except asyncio.TimeoutError:
                last_error = "Request timeout"
                logger.warning("Webhook request timed out")
                continue
            except Exception as e:
                last_error = f"Unexpected error: {str(e)}"
                logger.error(f"Webhook unexpected error: {e}", exc_info=True)
                continue

        elapsed_ms = (time.time() - start_time) * 1000
        return WebhookResult(
            success=False,
            error=last_error,
            elapsed_ms=elapsed_ms,
            retries=retries,
        )

    def _calculate_delay(self, attempt: int) -> float:
        """
        Calculate retry delay with exponential backoff and jitter.

        Args:
            attempt: Current attempt number (1-based)

        Returns:
            Delay in seconds
        """
        # Exponential backoff
        delay = min(self.base_delay * (2 ** (attempt - 1)), self.max_delay)
        # Add jitter
        jitter = delay * self.jitter_factor * (random.random() * 2 - 1)
        return max(0.1, delay + jitter)

    async def close(self):
        """Close the HTTP session and release resources."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
            logger.debug("Webhook client session closed")


async def close_webhook_client():
    """Close the global webhook client instance."""
    global _webhook_client
    if _webhook_client:
        await _webhook_client.close()
        _webhook_client = None
