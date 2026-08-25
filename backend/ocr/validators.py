"""
Reusable file-validation utilities for the OCR application.

These functions are intentionally framework-agnostic — they accept plain
integers/strings, not Django/DRF objects — so they can be reused from
serializers, services, or management commands without coupling.

Validation now delegates to the central format registry (``ocr.formats``)
so supported formats are defined in exactly one place.
"""

from __future__ import annotations

import os

from ocr.exceptions import InvalidFileException, UnsupportedFormatException
from ocr.formats import SUPPORTED_FORMATS, detect_format, get_supported_extensions, get_supported_mime_types
from ocr.adapters import get_adapter
from ocr.formats import FormatEntry

# ------------------------------------------------------------------
# Constants
# ------------------------------------------------------------------

#: Maximum allowed upload size in bytes (10 MB).
MAX_FILE_SIZE: int = 10 * 1024 * 1024

# Backward-compatible aliases used by existing tests and serializers.
ALLOWED_EXTENSIONS: frozenset[str] = frozenset(get_supported_extensions())
ALLOWED_MIME_TYPES: frozenset[str] = get_supported_mime_types()

# Mapping from MIME type to canonical file extension.
MIME_TYPE_TO_EXTENSION: dict[str, str] = {
    entry.mime_types[0]: ext
    for ext, entry in SUPPORTED_FORMATS.items()
}

# ------------------------------------------------------------------
# Utility Functions
# ------------------------------------------------------------------

def get_extension_from_filename(filename: str) -> str:
    """
    Extract the lowercase extension from a filename.

    Args:
        filename: A filename like ``invoice.PDF``.

    Returns:
        The lowercase extension without the dot (e.g. ``pdf``), or an
        empty string if the filename has no extension.

    Raises:
        InvalidFileException: If the filename is empty or None.
    """
    if not filename:
        raise InvalidFileException('Filename is empty or None.')
    if '.' not in filename:
        raise InvalidFileException(
            'File has no extension. '
            f'Allowed extensions: {", ".join(sorted(ALLOWED_EXTENSIONS))}.'
        )
    return filename.rsplit('.', 1)[-1].lower()

def get_extension_from_mime_type(mime_type: str) -> str:
    """
    Get the canonical file extension for a validated MIME type.

    Args:
        mime_type: A validated MIME type (e.g. ``application/pdf``).

    Returns:
        The canonical extension (e.g. ``pdf``).

    Raises:
        InvalidFileException: If the MIME type is not in the allowed set.
    """
    validate_mime_type(mime_type)
    return MIME_TYPE_TO_EXTENSION.get(mime_type, '')

# ------------------------------------------------------------------
# Validators
# ------------------------------------------------------------------

def validate_file_size(file_size: int, max_size: int = MAX_FILE_SIZE) -> None:
    """
    Validate that ``file_size`` (in bytes) does not exceed ``max_size``.

    Args:
        file_size: Size of the uploaded file in bytes.
        max_size: Maximum allowed size in bytes (default 10 MB).

    Raises:
        InvalidFileException: If the file exceeds the limit.
    """
    if file_size > max_size:
        raise InvalidFileException(
            f'File size {file_size} bytes exceeds the maximum '
            f'allowed size of {max_size} bytes ({max_size // (1024 * 1024)} MB).'
        )


def validate_extension(filename: str) -> None:
    """
    Validate that ``filename`` has an allowed extension.

    The check is case-insensitive: ``.PDF`` and ``.pdf`` are both accepted.

    Args:
        filename: Original name of the uploaded file.

    Raises:
        InvalidFileException: If the extension is missing or not allowed.
    """
    extension = get_extension_from_filename(filename)
    if extension not in ALLOWED_EXTENSIONS:
        raise InvalidFileException(
            f'File extension ".{extension}" is not allowed. '
            f'Allowed extensions: {", ".join(sorted(ALLOWED_EXTENSIONS))}.'
        )

def validate_mime_type(mime_type: str) -> None:
    """
    Validate that ``mime_type`` is in the allowed set.

    This is a deeper check than ``validate_extension`` — a malicious
    client can rename a ``.exe`` to ``.pdf``, but the MIME type
    (derived from file content by the server) will still betray it.

    Args:
        mime_type: MIME type string (e.g. ``application/pdf``).

    Raises:
        InvalidFileException: If the MIME type is not allowed.
    """
    if not mime_type:
        raise InvalidFileException(
            'File has no MIME type. '
            f'Allowed MIME types: {", ".join(sorted(ALLOWED_MIME_TYPES))}.'
        )

    if mime_type not in ALLOWED_MIME_TYPES:
        raise InvalidFileException(
            f'MIME type "{mime_type}" is not allowed. '
            f'Allowed MIME types: {", ".join(sorted(ALLOWED_MIME_TYPES))}.'
        )


def validate_file_format(file_path: str | Path, original_filename: str) -> dict:
    """
    Validate a file using the central format registry.

    Checks:
    1. Extension is supported
    2. MIME type matches the extension
    3. File size is within format-specific limits
    4. File content matches expected format (adapter validation)

    Args:
        file_path: Path to the uploaded file.
        original_filename: Original filename for extension check.

    Returns:
        A dict with ``is_valid`` and ``errors``.

    Raises:
        UnsupportedFormatException: If the format is not supported.
    """
    errors = []

    try:
        validate_extension(original_filename)
    except InvalidFileException as exc:
        errors.append(str(exc))

    try:
        fmt = detect_format(file_path)
    except UnsupportedFormatException as exc:
        errors.append(str(exc))
        return {'is_valid': False, 'errors': errors}

    try:
        file_size = os.path.getsize(file_path)
        validate_file_size(file_size, fmt.max_file_size_mb * 1024 * 1024)
    except InvalidFileException as exc:
        errors.append(str(exc))

    try:
        adapter = get_adapter(file_path, upload_id='validation')
        adapter.validate_security()
    except Exception as exc:
        errors.append(str(exc))

    return {'is_valid': len(errors) == 0, 'errors': errors}


def get_format_for_file(file_path: str | Path) -> FormatEntry | None:
    """
    Return the format entry for a file, or None if unsupported.
    """
    try:
        return detect_format(file_path)
    except UnsupportedFormatException:
        return None
