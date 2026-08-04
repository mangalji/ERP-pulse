"""
Service layer for the OCR application.

``OCRService`` owns all OCR business logic. Views validate input via
serializers and delegate to this class — they never touch storage,
providers, or models directly.

Phase 2 implements ``upload()`` — the full file-storage pipeline with
SHA256 hashing, extension extraction, and transaction safety.
``extract()`` and ``save_result()`` remain stubs for a later phase.
"""

from __future__ import annotations

from django.core.files.uploadedfile import UploadedFile
import hashlib
from django.db import transaction
from ocr.utils import logger
import time, uuid
from ocr.models import OCRUpload
from ocr.validators import (
    get_extension_from_mime_type,
    validate_extension,
    validate_file_size,
    validate_mime_type,
)

class OCRService:
    """
    Business-logic service for invoice OCR.

     The class is instantiated once at module load (see the ``ocr_service``
    singleton at the bottom) and reused across requests, matching the
    pattern used by ``AuthenticationService`` in the accounts app.
    """

    def upload(self, *, file: UploadedFile, user) -> OCRUpload:
        """
        Accept an uploaded invoice file, validate it, compute its SHA256
        hash, store it on disk, and persist an ``OCRUpload`` record —
        all inside a single database transaction.

        The original filename is **never** trusted for storage — a
        UUID-based name is generated so the on-disk path is fully
        controlled by the server. The original filename is preserved
        in the ``original_filename`` column for display purposes.

        If the database write fails after the file has been saved to
        disk, the file is cleaned up so no orphaned files remain.

        Args:
            file: The uploaded file object from the request.
            user: The authenticated user initiating the upload.

        Returns:
            OCRUpload: The persisted upload record.

        Raises:
            InvalidFileException: If extension, size, or MIME type
                validation fails.
        """
        start = time.perf_counter()

        original_filename: str = file.name
        file_size: int = file.size
        mime_type: str = file.content_type

        validate_extension(original_filename)
        validate_file_size(file_size)
        validate_mime_type(mime_type)

        extension = get_extension_from_mime_type(mime_type)
        stored_filename = self._generate_stored_filename(mime_type)
        file_hash = self._compute_sha256(file)

        # Override the uploaded file's name with the safe, server-generated
        # filename so Django's storage backend stores it as
        # <MEDIA_ROOT>/ocr/<uuid_hex>.<ext> — never under the original name.
        file.name = stored_filename

        try:
            with transaction.atomic():

                upload = OCRUpload.objects.create(
                    user=user,
                    original_filename=original_filename,
                    stored_filename=stored_filename,
                    file=file,
                    file_size=file_size,
                    mime_type=mime_type,
                    extension = extension,
                    file_hash=file_hash,
                    status=OCRUpload.Status.UPLOADED,
                )
        except Exception:
            # Database write failed — clean up the orphaned file so
            # disk storage doesn't accumulate files with no DB record.
            self._cleanup_orphaned_file(file)
            raise

        duration_ms = (time.perf_counter() - start) * 1000
        logger.info(
            'OCR upload completed — user=%s upload_id=%s filename=%s '
            'size=%d bytes mime=%s hash=% duration=%.2fms',
            user.id,
            upload.id,
            original_filename,
            file_size,
            mime_type,
            file_hash,
            duration_ms,
        )

        return upload

    def extract(self, *, upload_id: str, user) -> dict:
        """
        Run OCR extraction on a previously uploaded file.

        Args:
            upload_id: Identifier of the stored upload.
            user: The authenticated user requesting extraction.

        Raises:
            NotImplementedError: OCR extraction is not implemented yet.
        """
        logger.info(
            'OCRService.extract() called by user %s for upload %s — not implemented.',
            getattr(user, 'id', None),
            upload_id,
        )
        raise NotImplementedError('OCR extraction is not implemented yet.')

    def save_result(self, *, upload_id: str, result: dict, user) -> dict:
        """
        Persist the extracted structured data for a given upload.

        Args:
            upload_id: Identifier of the upload whose result to save.
            result: The structured data returned by ``extract``.
            user: The authenticated user saving the result.

        Raises:
            NotImplementedError: Result persistence is not implemented yet.
        """
        logger.info(
            'OCRService.save_result() called by user %s for upload %s — not implemented.',
            getattr(user, 'id', None),
            upload_id,
        )
        raise NotImplementedError('OCR result persistence is not implemented yet.')

    @staticmethod
    def _generate_stored_filename(extension: str) -> str:
        """
        Generate a safe, unique on-disk filename from the file extension.

        The filename is ``<uuid4_hex>.<ext>`` where ``<ext>`` is the
        validated extension — never derived from the user-supplied
        filename. This prevents path traversal and collision attacks.

        Args:
            extension: A validated, lowercase extension (e.g. ``pdf``).

        Returns:
            A safe filename like ``a1b2c3d4e5f6....pdf``.
        """
        return f'{uuid.uuid4().hex}.{extension}'

    @staticmethod
    def _compute_sha256(file:UploadedFile) -> str:
        """
        Compute the SHA256 hash of the uploaded file's content.

        The file is read in chunks to avoid loading the entire file
        into memory — important for files near the 10 MB limit.

        After reading, the file pointer is rewound to position 0 so
        that Django's ``FileField`` can re-read the content when
        saving the model. Closing the file here would cause
        ``ValueError: I/O operation on closed file`` during
        ``OCRUpload.objects.create()``.

        Args:
            file: The uploaded file object.

        Returns:
            The hex-encoded SHA256 digest (64 characters).
        """
        hasher = hashlib.sha256()
        file.open('rb')
        try:
            for chunk in iter(lambda: file.read(8192),b''):
                hasher.update(chunk)
        finally:
            file.seek(0)
        return hasher.hexdigest()

    @staticmethod
    def _cleanup_orphaned_file(file: UploadedFile) -> None:
        """
        Delete a file that was saved to disk but whose DB record failed.

        Swallows storage errors — a failed cleanup must never mask the
        original database exception that triggered it.

        Args:
            file: The file object whose on-disk copy should be removed.
        """
        try:
            file.storage.delete(file.name)
        except Exception:
            logger.exception(
                'Failed to clean up orphaned file %s after DB failure.',
                getattr(file, 'name', '<unknown>'),
            )

#: Module-level singleton, mirroring the pattern in accounts/views.py.
ocr_service = OCRService()