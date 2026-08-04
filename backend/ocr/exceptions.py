"""
Custom exceptions for the OCR application.

All exceptions declare a ``status_code`` attribute so the project-wide
``common.exception_handler.standard_exception_handler`` can wrap them into
the standard ``{"success": false, "message": "...", "data": {}}`` envelope
without importing this module.
"""

from rest_framework import status

class OCRException(Exception):
    """
    Base exception for all OCR-related errors.

    Every other OCR exception should inherit from this class so callers
    can catch the entire family with a single ``except OCRException``.
    """

    status_code = status.HTTP_400_BAD_REQUEST


class InvalidFileException(OCRException):
    """
    Raised when an uploaded file fails validation."""

    status_code = status.HTTP_400_BAD_REQUEST

class OCRServiceException(OCRException):
    """
    Raised when the OCR service encounters an internal failure.
    """

    status_code = status.HTTP_502_BAD_GATEWAY

class PDFTooLargeException(OCRException):
    """
    Raised when a PDF exceeds the maximum allowed page count.
    """

    status_code = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE


class PDFProcessingException(OCRException):
    """
    Raised when a PDF cannot be opened, parsed, or rendered.
    """

    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY

class InvalidImageException(OCRException):
    """
    Raised when an image file fails validation.
    """

    status_code = status.HTTP_400_BAD_REQUEST


class ImageProcessingException(OCRException):
    """
    Raised when the image processing pipeline encounters an internal
    failure.
    """

    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR

class GeminiConnectionException(OCRException):
    """
    Raised when the Gemini API cannot be reached — network error,
    DNS failure, or the service is unavailable.

    Maps to HTTP 502 (Bad Gateway) because the upstream AI provider
    is unreachable.
    """
    status_code = status.HTTP_502_BAD_GATEWAY


class GeminiTimeoutException(OCRException):
    """
    Raised when a Gemini API request exceeds the configured timeout.

    Maps to HTTP 504 (Gateway Timeout) because the upstream provider
    did not respond in time.
    """
    status_code = status.HTTP_504_GATEWAY_TIMEOUT


class GeminiValidationException(OCRException):
    """
    Raised when Gemini returns a response that cannot be parsed as
    valid JSON or fails schema validation.

    Maps to HTTP 422 (Unprocessable Entity) because the response
    format was invalid.
    """
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY


class GeminiRateLimitException(OCRException):
    """
    Raised when Gemini returns HTTP 429 (Too Many Requests).

    Maps to HTTP 429 because the client should back off.
    """
    status_code = status.HTTP_429_TOO_MANY_REQUESTS


class OCRExtractionFailedException(OCRException):
    """
    Raised when the OCR extraction pipeline fails.

    Maps to HTTP 500 because the failure originates server-side.
    """
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
