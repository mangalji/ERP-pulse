"""
Reusable file-validation utilities for the OCR application.

These functions are intentionally framework-agnostic — they accept plain
integers/strings, not Django/DRF objects — so they can be reused from
serializers, services, or management commands without coupling.
"""

from __future__ import annotations

from ocr.exceptions import InvalidFileException

# ------------------------------------------------------------------
# Constants
# ------------------------------------------------------------------

#: Maximum allowed upload size in bytes (10 MB).
MAX_FILE_SIZE: int = 10 * 1024 * 1024

#: File extensions accepted by the OCR pipeline.
ALLOWED_EXTENSIONS: frozenset[str] = frozenset(
    {
        'pdf',
        'png',
        'jpg',
        'jpeg',
        'webp',
    }
)

#: MIME types accepted by the OCR pipeline.
ALLOWED_MIME_TYPES: frozenset[str] = frozenset(
    {
        'application/pdf',
        'image/png',
        'image/jpeg',
        'image/webp',
    }
)

#: Mapping from MIME type to canonical file extension.
MIME_TYPE_TO_EXTENSION: dict[str, str] = {
    'application/pdf': 'pdf',
    'image/png': 'png',
    'image/jpeg': 'jpg',
    'image/webp': 'webp',
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
    return MIME_TYPE_TO_EXTENSION[mime_type]

# ------------------------------------------------------------------
# Validators
# ------------------------------------------------------------------

def validate_file_size(file_size: int) -> None:
    """
    Validate that ``file_size`` (in bytes) does not exceed ``MAX_FILE_SIZE``.

    Args:
        file_size: Size of the uploaded file in bytes.

    Raises:
        InvalidFileException: If the file exceeds the 10 MB limit.
    """
    if file_size > MAX_FILE_SIZE:
        raise InvalidFileException(
            f'File size {file_size} bytes exceeds the maximum '
            f'allowed size of {MAX_FILE_SIZE} bytes (10 MB).'
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