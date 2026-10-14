"""
Failure taxonomy for OCR processing.

Every OCR failure is mapped to a small, stable set of codes plus a
user-safe message. Raw exception text (which can contain provider payloads,
paths or other internals) is only ever written to logs, never stored as the
user-visible failure reason - except for file/validation problems whose
messages are written for end users.

``expected`` failures (quota, timeouts, bad files, missing services) are
logged as a one-line warning. Only genuinely ``unexpected`` failures get a
traceback in the logs.
"""

from __future__ import annotations

from dataclasses import dataclass

import redis

from ocr.exceptions import (
    DocumentProcessingException,
    GeminiConnectionException,
    GeminiRateLimitException,
    GeminiTimeoutException,
    GeminiValidationException,
    InvalidExtractionResultException,
    InvalidFileException,
    PDFProcessingException,
    PDFTooLargeException,
    UnsupportedFormatException,
)


class FailureCode:
    INVALID_FILE = "INVALID_FILE"
    QUOTA_EXHAUSTED = "QUOTA_EXHAUSTED"
    RATE_LIMITED = "RATE_LIMITED"
    TIMEOUT = "TIMEOUT"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    INVALID_RESPONSE = "INVALID_RESPONSE"
    INFRA_UNAVAILABLE = "INFRA_UNAVAILABLE"
    INTERNAL = "INTERNAL"


@dataclass(frozen=True)
class FailureInfo:
    code: str
    retryable: bool
    message: str  # safe to show to end users
    expected: bool = True  # False => log a traceback


_DAILY_QUOTA_MARKERS = (
    "generate_content_free_tier_requests",
    "generaterequestsperdaypermodel-freetier",
    "generaterequestsperdayperprojectpermodel-freetier",
    "daily quota",
    "quota exceeded for metric",
)

QUOTA_MESSAGE = (
    "Gemini daily API quota has been exhausted. Please try again after the "
    "quota resets or use an available Gemini API plan/model."
)

_FILE_ERRORS = (
    InvalidFileException,
    UnsupportedFormatException,
    PDFTooLargeException,
    PDFProcessingException,
    DocumentProcessingException,
)


def is_daily_quota_error(exc: BaseException) -> bool:
    """True for a project/model daily-quota exhaustion response (terminal)."""
    message = str(exc).lower()
    return any(marker in message for marker in _DAILY_QUOTA_MARKERS)


def _is_infra_error(exc: BaseException) -> bool:
    if isinstance(exc, redis.RedisError):
        return True
    try:  # kombu is only present when Celery is installed
        from kombu.exceptions import OperationalError as KombuOperationalError

        return isinstance(exc, KombuOperationalError)
    except ImportError:  # pragma: no cover
        return False


def classify_failure(exc: BaseException) -> FailureInfo:
    """Map any exception to a ``FailureInfo``."""
    if isinstance(exc, GeminiRateLimitException):
        if is_daily_quota_error(exc):
            return FailureInfo(FailureCode.QUOTA_EXHAUSTED, False, QUOTA_MESSAGE)
        return FailureInfo(
            FailureCode.RATE_LIMITED,
            True,
            "The AI provider is rate limiting requests. Please retry shortly.",
        )

    if isinstance(exc, (GeminiTimeoutException, TimeoutError)):
        return FailureInfo(
            FailureCode.TIMEOUT,
            True,
            "The AI provider took too long to respond.",
        )

    if isinstance(exc, GeminiConnectionException):
        return FailureInfo(
            FailureCode.PROVIDER_UNAVAILABLE,
            True,
            "The AI provider is temporarily unreachable.",
        )

    if isinstance(exc, (GeminiValidationException, InvalidExtractionResultException)):
        return FailureInfo(
            FailureCode.INVALID_RESPONSE,
            False,
            "The AI response could not be understood. Please try again.",
        )

    if isinstance(exc, _FILE_ERRORS):
        # These messages are written for end users.
        return FailureInfo(FailureCode.INVALID_FILE, False, str(exc) or "Invalid file.")

    if _is_infra_error(exc):
        return FailureInfo(
            FailureCode.INFRA_UNAVAILABLE,
            True,
            "A required service is temporarily unavailable. Please try again.",
        )

    return FailureInfo(
        FailureCode.INTERNAL,
        False,
        "OCR processing failed unexpectedly. Please try again or contact support.",
        expected=False,
    )
