"""
Webhook context registry for managing active webhook sessions.
Provides thread-safe storage and retrieval of WebhookContext objects.
"""

import threading
from typing import Optional
import logging

from .types import WebhookContext

logger = logging.getLogger(__name__)

# Thread-safe registry for webhook contexts
_context_lock = threading.RLock()
_webhook_contexts: dict[str, WebhookContext] = {}


def register_webhook_context(context: WebhookContext) -> None:
    """
    Register a webhook context for output interception.

    Args:
        context: The WebhookContext to register
    """
    with _context_lock:
        if context.prompt_id:
            _webhook_contexts[context.prompt_id] = context
            logger.debug(f"Registered webhook context for prompt {context.prompt_id}")
        else:
            logger.warning("Cannot register webhook context without prompt_id")


def get_webhook_context(prompt_id: str) -> Optional[WebhookContext]:
    """
    Get a registered webhook context by prompt ID.

    Args:
        prompt_id: The prompt ID to look up

    Returns:
        The WebhookContext if found, None otherwise
    """
    with _context_lock:
        return _webhook_contexts.get(prompt_id)


def unregister_webhook_context(prompt_id: str) -> Optional[WebhookContext]:
    """
    Remove and return a webhook context from the registry.

    Args:
        prompt_id: The prompt ID to unregister

    Returns:
        The removed WebhookContext if found, None otherwise
    """
    with _context_lock:
        context = _webhook_contexts.pop(prompt_id, None)
        if context:
            logger.debug(f"Unregistered webhook context for prompt {prompt_id}")
        return context


def get_all_contexts() -> dict[str, WebhookContext]:
    """
    Get a copy of all registered contexts.
    Useful for debugging and monitoring.

    Returns:
        Dictionary mapping prompt_id to WebhookContext
    """
    with _context_lock:
        return dict(_webhook_contexts)


def clear_all_contexts() -> int:
    """
    Clear all registered contexts.
    Useful for testing and cleanup.

    Returns:
        Number of contexts that were cleared
    """
    with _context_lock:
        count = len(_webhook_contexts)
        _webhook_contexts.clear()
        logger.debug(f"Cleared {count} webhook contexts")
        return count
