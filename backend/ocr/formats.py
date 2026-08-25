"""
Central supported-format registry for the OCR application.

This module defines the single source of truth for every document format
the ingestion pipeline may accept.  Callers should never hard-code
extension or MIME checks; they should consult the registry so future
format additions require only a single change here.
"""

from __future__ import annotations

import mimetypes
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional


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
