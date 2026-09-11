from __future__ import annotations
import os
import mimetypes
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional
from ocr.exceptions import InvalidFileException, UnsupportedFormatException
# ------------------------------------------------------------------
# Format categories
# ------------------------------------------------------------------

class FormatCategory(str, Enum):
    DOCUMENT = 'document'
    IMAGE = 'image'
    SPREADSHEET = 'spreadsheet'
    TEXT = 'text'


# ------------------------------------------------------------------
# Registry entry
# ------------------------------------------------------------------

@dataclass(frozen=True)
class FormatEntry:
    """
    Describes one supported document format.
    """
    extension: str
    mime_types: tuple[str, ...]
    category: FormatCategory
    label: str
    adapter: str
    max_file_size_mb: int = 10
    description: str = ''


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _guess_mime(path: Path) -> Optional[str]:
    mime, _ = mimetypes.guess_type(str(path))
    return mime


def detect_format(file_path: str | Path) -> FormatEntry:
    """
    Detect the format of a file from its extension and MIME type.

    Args:
        file_path: Path to the uploaded file.

    Returns:
        The matching ``FormatEntry``.

    Raises:
        UnsupportedFormatException: If the file's extension or MIME type
            is not in the supported registry.
    """
    from ocr.exceptions import UnsupportedFormatException

    path = Path(file_path)
    ext = path.suffix.lower().lstrip('.')
    if not ext:
        raise UnsupportedFormatException(
            'File has no extension. '
            f'Allowed extensions: {", ".join(sorted(SUPPORTED_FORMATS.keys()))}.'
        )

    entry = SUPPORTED_FORMATS.get(ext)
    if entry is None:
        raise UnsupportedFormatException(
            f'Extension ".{ext}" is not supported. '
            f'Allowed extensions: {", ".join(sorted(SUPPORTED_FORMATS.keys()))}.'
        )

    mime = _guess_mime(path)
    if mime and mime not in entry.mime_types:
        raise UnsupportedFormatException(
            f'MIME type "{mime}" does not match extension ".{ext}". '
            f'Expected one of: {", ".join(entry.mime_types)}.'
        )

    return entry


def lookup_format(extension: str, mime_type: str) -> FormatEntry:
    """
    Look up a format entry from extension and MIME type.

    This is useful for request-time validation where the file path
    may not yet be available.

    Args:
        extension: File extension without the dot.
        mime_type: MIME type string.

    Returns:
        The matching ``FormatEntry``.

    Raises:
        UnsupportedFormatException: If the extension or MIME type is
            not supported, or if they mismatch.
    """
    from ocr.exceptions import UnsupportedFormatException

    ext = extension.lower().lstrip('.')
    if not ext:
        raise UnsupportedFormatException(
            'File has no extension. '
            f'Allowed extensions: {", ".join(sorted(SUPPORTED_FORMATS.keys()))}.'
        )

    entry = SUPPORTED_FORMATS.get(ext)
    if entry is None:
        raise UnsupportedFormatException(
            f'Extension ".{ext}" is not supported. '
            f'Allowed extensions: {", ".join(sorted(SUPPORTED_FORMATS.keys()))}.'
        )

    if mime_type and mime_type not in entry.mime_types:
        raise UnsupportedFormatException(
            f'MIME type "{mime_type}" does not match extension ".{ext}". '
            f'Expected one of: {", ".join(entry.mime_types)}.'
        )

    return entry


def is_supported_extension(extension: str) -> bool:
    return extension.lower().lstrip('.') in SUPPORTED_FORMATS


def get_supported_extensions() -> list[str]:
    return sorted(SUPPORTED_FORMATS.keys())


def get_supported_mime_types() -> frozenset[str]:
    return frozenset(
        mime for entry in SUPPORTED_FORMATS.values() for mime in entry.mime_types
    )


# ------------------------------------------------------------------
# Supported formats registry
# ------------------------------------------------------------------
# Only formats that can be reliably processed by the current stack are
# listed here.  If a parser is unavailable or the format is unsafe, the
# format is intentionally omitted.

SUPPORTED_FORMATS: dict[str, FormatEntry] = {
    # Documents
    'pdf': FormatEntry(
        extension='pdf',
        mime_types=('application/pdf',),
        category=FormatCategory.DOCUMENT,
        label='PDF',
        adapter='pdf',
        max_file_size_mb=20,
        description='Portable Document Format',
    ),
    'docx': FormatEntry(
        extension='docx',
        mime_types=(
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        ),
        category=FormatCategory.DOCUMENT,
        label='DOCX',
        adapter='docx',
        max_file_size_mb=20,
        description='Word Open XML Document',
    ),
    # Images
    'jpg': FormatEntry(
        extension='jpg',
        mime_types=('image/jpeg',),
        category=FormatCategory.IMAGE,
        label='JPEG',
        adapter='image',
        max_file_size_mb=20,
        description='JPEG image',
    ),
    'jpeg': FormatEntry(
        extension='jpeg',
        mime_types=('image/jpeg',),
        category=FormatCategory.IMAGE,
        label='JPEG',
        adapter='image',
        max_file_size_mb=20,
        description='JPEG image',
    ),
    'png': FormatEntry(
        extension='png',
        mime_types=('image/png',),
        category=FormatCategory.IMAGE,
        label='PNG',
        adapter='image',
        max_file_size_mb=20,
        description='PNG image',
    ),
    'webp': FormatEntry(
        extension='webp',
        mime_types=('image/webp',),
        category=FormatCategory.IMAGE,
        label='WEBP',
        adapter='image',
        max_file_size_mb=20,
        description='WEBP image',
    ),
    'gif': FormatEntry(
        extension='gif',
        mime_types=('image/gif',),
        category=FormatCategory.IMAGE,
        label='GIF',
        adapter='image',
        max_file_size_mb=20,
        description='GIF image',
    ),
    'bmp': FormatEntry(
        extension='bmp',
        mime_types=('image/bmp', 'image/x-windows-bmp'),
        category=FormatCategory.IMAGE,
        label='BMP',
        adapter='image',
        max_file_size_mb=20,
        description='Bitmap image',
    ),
    'tif': FormatEntry(
        extension='tif',
        mime_types=('image/tiff',),
        category=FormatCategory.IMAGE,
        label='TIFF',
        adapter='image',
        max_file_size_mb=20,
        description='TIFF image',
    ),
    'tiff': FormatEntry(
        extension='tiff',
        mime_types=('image/tiff',),
        category=FormatCategory.IMAGE,
        label='TIFF',
        adapter='image',
        max_file_size_mb=20,
        description='TIFF image',
    ),
    # Spreadsheets
    'xlsx': FormatEntry(
        extension='xlsx',
        mime_types=(
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        ),
        category=FormatCategory.SPREADSHEET,
        label='XLSX',
        adapter='spreadsheet',
        max_file_size_mb=10,
        description='Excel Open XML Workbook',
    ),
    'csv': FormatEntry(
        extension='csv',
        mime_types=(
            'text/csv',
            'text/plain',
            'application/csv',
            'application/vnd.ms-excel',
        ),
        category=FormatCategory.SPREADSHEET,
        label='CSV',
        adapter='csv',
        max_file_size_mb=10,
        description='Comma-separated values',
    ),
    # Text
    'txt': FormatEntry(
        extension='txt',
        mime_types=('text/plain',),
        category=FormatCategory.TEXT,
        label='TXT',
        adapter='text',
        max_file_size_mb=5,
        description='Plain text',
    ),
}


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
        from ocr.adapters import get_adapter
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
