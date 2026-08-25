"""
OCR upload service.

Provides the ``upload()`` method used by ``UploadView`` to persist an
uploaded file as an ``OCRUpload`` record: storing the file, deriving the
extension from the MIME type, computing the SHA256 hash, and recording
the upload metadata. Business logic lives here — views stay thin.

``OCRService`` is retained for backward compatibility as a thin facade
over the real extraction entry point (``OCRExtractionService``). It does
NOT re-implement extraction — it delegates so ``OCRExtractionService``
remains the single source of truth for the OCR/AI pipeline.
"""

from __future__ import annotations

import hashlib
import os
import uuid
import tempfile

from django.db import transaction

from ocr.models import OCRUpload
from ocr.utils import logger
from ocr.validators import (
    get_extension_from_mime_type,
    validate_extension,
    validate_file_size,
    validate_mime_type,
    validate_file_format,
)
from ocr.formats import lookup_format
from ocr.exceptions import InvalidFileException, UnsupportedFormatException, DocumentProcessingException


class OCRService:
    """
    Upload persistence and a thin facade over OCR extraction.

    ``upload`` persists an uploaded file as an ``OCRUpload`` record.
    ``extract`` and ``save_result`` delegate to ``OCRExtractionService``
    so the full extraction pipeline is never duplicated here.
    """

    def __init__(self, extraction_service=None) -> None:
        # Lazy-import to avoid a circular import at module load time.
        self._extraction_service = extraction_service

    def _extractor(self):
        """Return the shared OCRExtractionService instance."""
        if self._extraction_service is None:
            from ocr.extraction_service import ocr_extraction_service
            self._extraction_service = ocr_extraction_service
        return self._extraction_service

    @transaction.atomic
    def upload(self, *, file, user) -> OCRUpload:
        """
        Persist an uploaded file as an ``OCRUpload`` record.

        Validates the file (size, extension, MIME type, format content),
        computes a SHA256 hash for duplicate detection, and stores the
        file under a unique UUID-based name.

        Args:
            file: The uploaded file (DRF ``UploadedFile``).
            user: The authenticated user.

        Returns:
            The created ``OCRUpload`` instance.

        Raises:
            InvalidFileException: If the file is oversized, has a
                disallowed extension, or an unsupported MIME type.
            UnsupportedFormatException: If the file format is not supported.
            DocumentProcessingException: If the file content is corrupt.
        """
        validate_extension(file.name)
        validate_mime_type(file.content_type)

        ext = file.name.rsplit('.', 1)[-1].lower()
        fmt = lookup_format(ext, file.content_type or '')
        validate_file_size(file.size, max_size=fmt.max_file_size_mb * 1024 * 1024)

        original_filename = file.name

        content = file.read()
        file_hash = hashlib.sha256(content).hexdigest()
        file.seek(0)

        extension = get_extension_from_mime_type(file.content_type)
        stored_filename = f'{uuid.uuid4().hex}.{extension}'

        # Write content to a temporary file for format validation.
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix=f'.{extension}') as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        try:
            validation = validate_file_format(tmp_path, original_filename)
            if not validation['is_valid']:
                raise InvalidFileException(
                    'File validation failed: ' + '; '.join(validation['errors'])
                )
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

        # Store the file under the UUID-based name, not the original,
        # so it cannot collide and does not leak the original filename.
        file.name = stored_filename

        upload = OCRUpload.objects.create(
            user=user,
            original_filename=original_filename,
            stored_filename=stored_filename,
            file=file,
            file_size=file.size,
            mime_type=file.content_type,
            extension=extension,
            file_hash=file_hash,
            status=OCRUpload.Status.UPLOADED,
        )

        logger.info(
            'Upload created — upload_id=%s user=%s size=%d',
            upload.id, user.id, file.size,
        )
        return upload

    def extract(self, *, upload_id, user):
        """
        Extract structured data from an upload.

        Thin delegation to ``OCRExtractionService`` — no extraction
        logic lives here. ``upload_id`` is resolved to an ``OCRUpload``
        before handing off to the extraction service.
        """
        upload = OCRUpload.objects.select_related('user').get(pk=upload_id)
        return self._extractor().extract(upload, user)

    def save_result(self, *, upload_id, result, user):
        """
        Persist an extraction result (delegated to the pipeline).

        Kept for backward compatibility; routes to the IDP pipeline's
        document persistence stage so callers do not bypass it.
        """
        from ocr.services.pipeline_service import idp_pipeline_service
        return idp_pipeline_service.process_upload(
            upload_id=upload_id,
            user=user,
        )


ocr_service = OCRService()
