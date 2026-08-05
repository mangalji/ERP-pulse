"""
Document persistence for the IDP engine.

Persists ``OCRDocument``, ``OCRDocumentPage``, and version snapshots.
Originals are never overwritten — each review/retry creates a new
version (the "immutable version snapshot" pattern from the model).
"""

from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from ocr.models import (
    OCRDocument,
    OCRDocumentPage,
    OCRDocumentStatus,
    OCRDocumentVersion,
)
from ocr.utils import logger


class DocumentService:
    """
    Persistence and lifecycle for ``OCRDocument`` entities.
    """

    @transaction.atomic
    def create_document(
        self,
        *,
        upload,
        user,
        company,
        document_type,
        status=OCRDocumentStatus.EXTRACTED,
        page_count=0,
        overall_confidence=None,
    ) -> OCRDocument:
        """Create a new ``OCRDocument`` from an upload."""
        document = OCRDocument.objects.create(
            upload=upload,
            user=user,
            company=company,
            document_type=document_type,
            status=status,
            page_count=page_count,
            overall_confidence=overall_confidence,
        )
        logger.info('OCRDocument created — id=%s upload=%s', document.id, upload.id)
        return document

    @transaction.atomic
    def save_document(
        self,
        *,
        document,
        raw_text,
        layout_blocks,
        normalized_json,
        reviewed_json=None,
        confidence=None,
        validation_errors=None,
        status=None,
    ) -> OCRDocumentVersion:
        """
        Persist a document snapshot and create a new version.

        The ``document`` current state is updated in place, and an
        immutable ``OCRDocumentVersion`` is created to preserve the
        history.
        """
        # Update document fields.
        if status is not None:
            document.status = status
        if normalized_json is not None:
            document.normalized_json = normalized_json
        if confidence is not None:
            document.overall_confidence = confidence.get('overall', document.overall_confidence)
        document.save()

        # Create version snapshot.
        version_number = (document.current_version or 0) + 1
        version = OCRDocumentVersion.objects.create(
            document=document,
            version_number=version_number,
            raw_ocr={'text': raw_text or ''},
            normalized_json=normalized_json or {},
            reviewed_json=reviewed_json or {},
            confidence=confidence or {},
            validation_errors=validation_errors or [],
        )
        document.current_version = version_number
        document.save(update_fields=['current_version'])

        logger.info(
            'OCRDocument snapshot saved — document=%s version=%d',
            document.id, version_number,
        )
        return version

    @transaction.atomic
    def create_pages(
        self,
        *,
        document,
        pages,
    ) -> list[OCRDocumentPage]:
        """Persist per-page records for a document."""
        created = []
        for page in pages:
            page_obj = OCRDocumentPage.objects.create(
                document=document,
                page_number=page.get('page_number', 0),
                raw_text=page.get('raw_text', ''),
                layout_blocks=page.get('layout_blocks', {}),
                is_blank=page.get('is_blank', False),
                is_duplicate=page.get('is_duplicate', False),
            )
            created.append(page_obj)
        logger.info('OCRDocument pages created — document=%s pages=%d', document.id, len(created))
        return created

    def update_status(self, *, document, status, failure_reason=None) -> OCRDocument:
        """Update the document lifecycle status."""
        document.status = status
        if status == OCRDocumentStatus.FAILED and failure_reason:
            document.failure_reason = failure_reason
        if status == OCRDocumentStatus.APPROVED:
            document.reviewed_at = timezone.now()
        document.save()
        return document


document_service = DocumentService()
