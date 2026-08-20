"""
Generic, reusable validators for AGSuite ERP.

Only cross-cutting validators belong here. Module-specific validation
(e.g., OTP format, NetSuite record IDs, file MIME types) stays in the
respective app's own validators module.

These validators are plain functions (not DRF serializer validators)
so they can be used both inside serializers and inside service-layer
code. They raise ``core.exceptions.ValidationException`` on failure,
which the existing ``common/exception_handler.py`` automatically
converts into a 400 response.
"""

import uuid

from core.constants import MAX_PAGE_SIZE, MIN_PAGE_SIZE
from core.exceptions import ValidationException


def validate_uuid(value: str, field_name: str = 'id') -> str:
    """
    Validate that a string is a valid UUID.

    Returns the canonical string form if valid.
    Raises ``ValidationException`` if the value is not a valid UUID.
    """
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, AttributeError, TypeError):
        raise ValidationException(f'{field_name} must be a valid UUID.')


def validate_positive_integer(
    value: int,
    field_name: str = 'value',
    minimum: int | None = None,
    maximum: int | None = None,
) -> int:
    """
    Validate that a value is a positive integer within optional bounds.

    Returns the validated integer.
    Raises ``ValidationException`` if the value is not a positive integer
    or falls outside the specified bounds.
    """
    try:
        int_value = int(value)
    except (ValueError, TypeError):
        raise ValidationException(f'{field_name} must be an integer.')

    if int_value < 0:
        raise ValidationException(f'{field_name} must be a positive integer.')

    if minimum is not None and int_value < minimum:
        raise ValidationException(f'{field_name} must be at least {minimum}.')

    if maximum is not None and int_value > maximum:
        raise ValidationException(f'{field_name} must be at most {maximum}.')

    return int_value


def validate_pagination_params(offset: int, limit: int) -> tuple[int, int]:
    """
    Validate and normalize pagination query parameters.

    Returns ``(offset, limit)`` clamped to safe bounds.
    Raises ``ValidationException`` if the values are not integers.
    """
    try:
        offset = int(offset)
    except (ValueError, TypeError):
        offset = 0

    try:
        limit = int(limit)
    except (ValueError, TypeError):
        limit = 20

    offset = max(0, offset)
    limit = max(MIN_PAGE_SIZE, min(limit, MAX_PAGE_SIZE))

    return offset, limit


def validate_non_empty_string(value: str, field_name: str = 'value') -> str:
    """
    Validate that a string is non-empty after stripping whitespace.

    Returns the stripped string.
    Raises ``ValidationException`` if the value is empty or not a string.
    """
    if not isinstance(value, str):
        raise ValidationException(f'{field_name} must be a string.')

    stripped = value.strip()
    if not stripped:
        raise ValidationException(f'{field_name} must not be empty.')

    return stripped