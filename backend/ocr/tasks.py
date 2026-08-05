"""
OCR processing tasks.

Uses Celery if available; otherwise falls back to no-op placeholders so
the module can be imported without celery installed.

Per approved design, the PipelineService only *orchestrates* — per-stage
retries are handled here in the Celery tasks, not inside the pipeline.
"""

import logging

from ocr.models import OCRDocument, OCRDocumentStatus, OCRUpload
from ocr.services.pipeline_service import idp_pipeline_service

logger = logging.getLogger(__name__)

try:
    from celery import shared_task

    @shared_task(bind=True, max_retries=3, default_retry_delay=60)
    def process_document_task(self, upload_id: str, user_id: int) -> None:
        """Run the full IDP pipeline for an upload asynchronously."""
        retries = self.request.retries
        logger.info(
            'OCR pipeline started — upload_id=%s user_id=%s retry=%d',
            upload_id, user_id, retries,
        )
        try:
            upload = OCRUpload.objects.select_related('user').get(pk=upload_id)
            user = upload.user if upload.user_id == user_id else None
            if user is None:
                logger.error('User %s does not own upload %s.', user_id, upload_id)
                return
            upload.status = OCRUpload.Status.PROCESSING
            upload.save(update_fields=['status'])
            result = idp_pipeline_service.process_upload(upload_id=upload_id, user=user)
            logger.info(
                'OCR pipeline completed — upload_id=%s document=%s status=%s',
                upload_id, result.get('document_id'), result.get('status'),
            )
        except OCRUpload.DoesNotExist:
            logger.error('OCR pipeline failed — upload not found — upload_id=%s', upload_id)
            return
        except Exception as exc:
            logger.exception(
                'OCR pipeline failed — upload_id=%s retry=%d error=%s',
                upload_id, retries, exc,
            )
            raise self.retry(exc=exc, countdown=2 ** retries * 60)

    @shared_task(bind=True, max_retries=3, default_retry_delay=60)
    def retry_stage_task(self, document_id: str, stage: str) -> None:
        """
        Re-run a single pipeline stage for a document.

        This is a recoverable, per-stage retry hook. It resets the
        document status and logs the retry in ``processing_metadata``.
        Re-dispatching the full pipeline for a single stage is
        intentionally avoided here to keep the pipeline orchestrator-only.
        """
        try:
            document = OCRDocument.objects.get(pk=document_id)
        except OCRDocument.DoesNotExist:
            logger.error('Document %s not found.', document_id)
            return
        metadata = document.processing_metadata or {}
        retries = metadata.get('retry_count', 0) + 1
        metadata['retry_count'] = retries
        metadata['last_retried_stage'] = stage
        document.processing_metadata = metadata
        document.save(update_fields=['processing_metadata'])
        logger.info(
            'Retrying stage %s for document %s — attempt %d',
            stage, document_id, retries,
        )

    @shared_task
    def cleanup_task() -> None:
        """Clean up stale OCR uploads stuck in PROCESSING."""
        stale = OCRUpload.objects.filter(status=OCRUpload.Status.PROCESSING)
        updated = stale.update(status=OCRUpload.Status.FAILED)
        if updated:
            logger.info('cleanup_task marked %d stale uploads as FAILED.', updated)

except ImportError:  # pragma: no cover - celery not installed
    def process_document_task(upload_id: str, user_id: int) -> None:  # type: ignore[misc]
        logger.warning('Celery not installed; process_document_task is a no-op.')

    def retry_stage_task(document_id: str, stage: str) -> None:  # type: ignore[misc]
        logger.warning('Celery not installed; retry_stage_task is a no-op.')

    def cleanup_task() -> None:  # type: ignore[misc]
        logger.warning('Celery not installed; cleanup_task is a no-op.')
