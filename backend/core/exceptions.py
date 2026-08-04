"""
Base exception hierarchy for ERP Pulse.

All exceptions inherit from ``ERPPulseException`` and set a
``status_code`` class attribute — the same convention the existing
``common/exception_handler.py`` already checks via
``getattr(exc, 'status_code', None)``. This means every exception
defined here is automatically handled by the existing exception handler
without any changes to that file.

Existing app-specific exceptions (``accounts/exceptions.py``,
``ai/exceptions.py``, ``netsuite/exceptions.py``, ``sync/exceptions.py``,
``ocr/exceptions.py``) are intentionally NOT migrated to inherit from
these base classes in this phase. They continue to inherit directly
from ``Exception`` so no existing imports break. New exceptions created
from Phase 0.3 onward should inherit from the appropriate base here.
"""

from rest_framework import status


class ERPPulseException(Exception):
    """
    Root exception for all ERP Pulse domain errors.

    Every other exception in this module inherits from this class.
    The ``status_code`` attribute is what ``common/exception_handler.py``
    reads to decide the HTTP response code — matching the convention
    already used by ``accounts/exceptions.py``.
    """

    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_message = 'An unexpected error occurred.'

    def __init__(self, message: str | None = None, **kwargs):
        self.message = message or self.default_message
        self.extra = kwargs
        super().__init__(self.message)


class ValidationException(ERPPulseException):
    """Raised when input validation fails at the service layer."""

    status_code = status.HTTP_400_BAD_REQUEST
    default_message = 'Validation failed.'


class BusinessException(ERPPulseException):
    """
    Raised when a business rule is violated (e.g., an operation is
    not allowed in the current state).

    Distinct from ``ValidationException``: the input may be well-formed,
    but the business context makes the operation invalid.
    """

    status_code = status.HTTP_400_BAD_REQUEST
    default_message = 'Business rule violation.'


class PermissionDeniedException(ERPPulseException):
    """Raised when a user lacks permission for the requested operation."""

    status_code = status.HTTP_403_FORBIDDEN
    default_message = 'You do not have permission to perform this action.'


class NotFoundException(ERPPulseException):
    """Raised when a requested resource does not exist."""

    status_code = status.HTTP_404_NOT_FOUND
    default_message = 'Resource not found.'


class ConflictException(ERPPulseException):
    """
    Raised when a request conflicts with the current state of the
    resource (e.g., duplicate unique value).
    """

    status_code = status.HTTP_409_CONFLICT
    default_message = 'A conflict occurred with the current state of the resource.'