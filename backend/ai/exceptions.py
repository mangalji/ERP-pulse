"""
AI module exceptions.

Each carries a `status_code` attribute — the same convention
accounts/exceptions.py and netsuite/exceptions.py already use — so
common/exception_handler.py can map them to the standard error envelope
without importing this module (common stays app-agnostic).
"""

from rest_framework import status


class AIProviderNotConfiguredException(Exception):
    """
    Raised when the configured AI provider has no API key set.
    Not a crash — a clean, typed error.
    """

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE


class AIProviderRequestException(Exception):
    """
    Raised when the AI provider's API call fails — network error,
    non-2xx response, or unexpected response shape.
    """

    status_code = status.HTTP_502_BAD_GATEWAY


class AIConversationNotFoundException(Exception):
    """
    Raised when a conversation_id is supplied that doesn't exist or
    doesn't belong to the requesting user.
    """

    status_code = status.HTTP_404_NOT_FOUND
