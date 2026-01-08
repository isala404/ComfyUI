"""Processors for input and output handling."""

from .inputs import WebhookInputProcessor
from .outputs import detect_output_type, get_output_path, process_outputs_for_webhook

__all__ = [
    "WebhookInputProcessor",
    "detect_output_type",
    "get_output_path",
    "process_outputs_for_webhook",
]
