"""Safe ZIP intake for OCR batch uploads."""

from __future__ import annotations

import mimetypes
import posixpath
import zipfile
from io import BytesIO

from django.core.files.uploadedfile import InMemoryUploadedFile
from django.conf import settings


class ZipValidationError(ValueError):
    """Raised when a ZIP archive is unsafe or contains unsupported content."""


_ALLOWED_EXTENSIONS = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}

_MAX_ZIP_FILES = getattr(settings, "OCR_MAX_ZIP_FILES", 20)
_MAX_ZIP_COMPRESSED_BYTES = (
    getattr(settings, "OCR_MAX_ZIP_SIZE_MB", 50) * 1024 * 1024
)
_MAX_ZIP_UNCOMPRESSED_BYTES = (
    getattr(settings, "OCR_MAX_ZIP_UNCOMPRESSED_MB", 100) * 1024 * 1024
)


def _normalise_member_name(name: str) -> str:
    return name.replace("\\", "/")


def _validate_member_name(name: str) -> str:
    normalized = _normalise_member_name(name)

    # Never allow absolute paths or traversal outside the extraction root.
    if normalized.startswith("/") or normalized.startswith("\\"):
        raise ZipValidationError(
            f"ZIP contains an unsafe absolute path: {name!r}."
        )

    parts = [part for part in normalized.split("/") if part]
    if ".." in parts:
        raise ZipValidationError(
            f"ZIP contains an unsafe path traversal entry: {name!r}."
        )

    safe_name = posixpath.basename(normalized)

    if not safe_name or safe_name in {".", ".."}:
        raise ZipValidationError(
            f"ZIP contains an invalid filename: {name!r}."
        )

    return safe_name


def extract_supported_files_from_zip(uploaded_file):
    """
    Validate and extract supported PDF/image members into memory.

    No OCRUpload is created here. The caller passes each resulting
    InMemoryUploadedFile through OCRService.upload(), preserving the existing
    validation/storage path.
    """
    if uploaded_file.size > _MAX_ZIP_COMPRESSED_BYTES:
        raise ZipValidationError(
            f"ZIP file is too large. Maximum allowed size is "
            f"{settings.OCR_MAX_ZIP_SIZE_MB} MB."
        )

    uploaded_file.seek(0)

    try:
        archive = zipfile.ZipFile(uploaded_file)
    except (zipfile.BadZipFile, OSError, ValueError) as exc:
        raise ZipValidationError("The uploaded ZIP archive is invalid.") from exc

    with archive:
        members = [
            info
            for info in archive.infolist()
            if not info.is_dir()
        ]

        if not members:
            raise ZipValidationError(
                "The ZIP archive contains no files."
            )

        if len(members) > _MAX_ZIP_FILES:
            raise ZipValidationError(
                f"ZIP contains {len(members)} files. Maximum allowed is "
                f"{_MAX_ZIP_FILES}."
            )

        total_uncompressed = 0
        prepared_members = []

        for info in members:
            safe_name = _validate_member_name(info.filename)

            if safe_name.lower().endswith(".zip"):
                raise ZipValidationError(
                    f"Nested ZIP archives are not allowed: {info.filename!r}."
                )

            extension = "." + safe_name.rsplit(".", 1)[-1].lower() if "." in safe_name else ""

            mime_type = _ALLOWED_EXTENSIONS.get(extension)
            if mime_type is None:
                raise ZipValidationError(
                    f"Unsupported file inside ZIP: {info.filename!r}. "
                    "Only PDF and supported image files are allowed."
                )

            if info.file_size <= 0:
                raise ZipValidationError(
                    f"File inside ZIP is empty: {info.filename!r}."
                )

            # Per-file size is ultimately checked again by OCRService.upload().
            # This early check prevents loading an oversized member into RAM.
            max_single_file = getattr(
                settings,
                "OCR_MAX_UPLOAD_SIZE_MB",
                10,
            ) * 1024 * 1024

            if info.file_size > max_single_file:
                raise ZipValidationError(
                    f"File inside ZIP exceeds the {settings.OCR_MAX_UPLOAD_SIZE_MB} MB "
                    f"per-file limit: {info.filename!r}."
                )

            total_uncompressed += info.file_size

            if total_uncompressed > _MAX_ZIP_UNCOMPRESSED_BYTES:
                raise ZipValidationError(
                    "The total uncompressed ZIP content exceeds the "
                    f"{settings.OCR_MAX_ZIP_UNCOMPRESSED_MB} MB limit."
                )

            prepared_members.append((info, safe_name, mime_type))

        result = []

        for info, safe_name, mime_type in prepared_members:
            with archive.open(info, "r") as member:
                data = member.read()

            size = len(data)
            if size != info.file_size:
                raise ZipValidationError(
                    f"ZIP member size changed while reading: {info.filename!r}."
                )

            content = BytesIO(data)

            result.append(
                InMemoryUploadedFile(
                    file=content,
                    field_name="files",
                    name=safe_name,
                    content_type=mime_type,
                    size=size,
                    charset=None,
                )
            )

        return result
