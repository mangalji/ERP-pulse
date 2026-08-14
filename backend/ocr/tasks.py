"""
OCR processing tasks.

Existing IDP pipeline tasks are preserved.
The test OCR batch processor uses the approved notebook Gemini extractor,
Redis quota limiting, and per-file persistence.
"""

from __future__ import annotations

import logging
import random

from django.utils import timezone

from ocr.exceptions import (
    GeminiConnectionException,
    GeminiRateLimitException,
    GeminiTimeoutException,
)
from ocr.models import OCRBatch, OCRDocument, OCRUpload
from ocr.notebook_extraction_service import notebook_gemini_extractor
from ocr.services.extraction_persistence import persist_extraction
from ocr.services.gemini_quota_limiter import GeminiQuotaLimiter
from ocr.services.pipeline_service import idp_pipeline_service

logger = logging.getLogger(__name__)


def _refresh_batch_status(batch_id):
    """Reconcile one batch from its child upload states."""
    try:
        batch = OCRBatch.objects.get(pk=batch_id)
    except OCRBatch.DoesNotExist:
        return

    uploads = OCRUpload.objects.filter(batch_id=batch_id)
    total = uploads.count()

    if total == 0:
        batch.status = OCRBatch.Status.FAILED
        batch.completed_at = timezone.now()
        batch.save(update_fields=["status", "completed_at"])
        return

    completed = uploads.filter(
        status=OCRUpload.Status.COMPLETED
    ).count()
    failed = uploads.filter(
        status=OCRUpload.Status.FAILED
    ).count()
    active = uploads.exclude(
        status__in=[
            OCRUpload.Status.COMPLETED,
            OCRUpload.Status.FAILED,
        ]
    ).exists()

    if completed == total:
        new_status = OCRBatch.Status.COMPLETED
    elif failed == total:
        new_status = OCRBatch.Status.FAILED
    elif failed and not active:
        new_status = OCRBatch.Status.PARTIAL
    else:
        new_status = OCRBatch.Status.PROCESSING

    update_fields = ["status"]
    batch.status = new_status

    if new_status in {
        OCRBatch.Status.COMPLETED,
        OCRBatch.Status.FAILED,
        OCRBatch.Status.PARTIAL,
    }:
        batch.completed_at = timezone.now()
        update_fields.append("completed_at")

    batch.save(update_fields=update_fields)


try:
    from celery import shared_task

    @shared_task(
        bind=True,
        max_retries=5,
        default_retry_delay=30,
        acks_late=True,
        reject_on_worker_lost=True,
    )
    def process_test_ocr_upload_task(
        self,
        upload_id: str,
        user_id: str,
    ) -> None:
        """
        Process one uploaded OCR file.

        Celery provides async execution. Redis provides a global
        concurrency/RPM limiter shared across all workers.
        """
        upload = None
        limiter = GeminiQuotaLimiter()
        token = None

        try:
            upload = OCRUpload.objects.select_related(
                "user",
                "batch",
            ).get(pk=upload_id)

            if str(upload.user_id) != str(user_id):
                logger.error(
                    "OCR task ownership mismatch — upload=%s user=%s upload_owner=%s",
                    upload_id,
                    user_id,
                    upload.user_id,
                )
                return

            if upload.status == OCRUpload.Status.COMPLETED:
                _refresh_batch_status(upload.batch_id)
                return

            upload.status = OCRUpload.Status.PROCESSING
            upload.processing_started_at = timezone.now()
            upload.processing_completed_at = None
            upload.failure_reason = None
            upload.save(
                update_fields=[
                    "status",
                    "processing_started_at",
                    "processing_completed_at",
                    "failure_reason",
                ]
            )

            # This is the distributed global gate. The actual Gemini call
            # starts only after both concurrency and rolling-RPM checks pass.
            token = limiter.acquire(
                request_id=f"{upload.id}:{self.request.id}"
            )

            result = notebook_gemini_extractor.extract(
                file_path=upload.file.path,
                mime_type=upload.mime_type,
            )

            document, version = persist_extraction(
                upload=upload,
                user=upload.user,
                result=result,
            )

            completed_at = timezone.now()
            upload.status = OCRUpload.Status.COMPLETED
            upload.processing_completed_at = completed_at
            upload.processing_duration_ms = int(
                (
                    completed_at
                    - upload.processing_started_at
                ).total_seconds()
                * 1000
            )
            upload.failure_reason = None
            upload.save(
                update_fields=[
                    "status",
                    "processing_completed_at",
                    "processing_duration_ms",
                    "failure_reason",
                ]
            )

            logger.info(
                "Test OCR completed — upload=%s document=%s version=%s",
                upload_id,
                document.id,
                version.version_number,
            )

            _refresh_batch_status(upload.batch_id)

        except (GeminiRateLimitException, GeminiTimeoutException, GeminiConnectionException) as exc:
            if upload is not None:
                upload.status = OCRUpload.Status.UPLOADED
                upload.failure_reason = str(exc)[:5000]
                upload.save(
                    update_fields=["status", "failure_reason"]
                )

            retries = self.request.retries
            countdown = min(
                15 * (2 ** retries) + random.uniform(0, 5),
                900,
            )

            logger.warning(
                "Retryable OCR failure — upload=%s retry=%d "
                "countdown=%.1fs error=%s",
                upload_id,
                retries,
                countdown,
                exc,
            )

            raise self.retry(exc=exc, countdown=countdown)

        except OCRUpload.DoesNotExist:
            logger.error(
                "Test OCR upload not found — upload_id=%s",
                upload_id,
            )

        except Exception as exc:
            logger.exception(
                "Test OCR processing failed — upload=%s error=%s",
                upload_id,
                exc,
            )

            if upload is not None:
                completed_at = timezone.now()
                upload.status = OCRUpload.Status.FAILED
                upload.processing_completed_at = completed_at
                upload.failure_reason = str(exc)[:5000]

                update_fields = [
                    "status",
                    "processing_completed_at",
                    "failure_reason",
                ]

                if upload.processing_started_at:
                    upload.processing_duration_ms = int(
                        (
                            completed_at
                            - upload.processing_started_at
                        ).total_seconds()
                        * 1000
                    )
                    update_fields.append("processing_duration_ms")

                upload.save(update_fields=update_fields)
                _refresh_batch_status(upload.batch_id)

        finally:
            if token is not None:
                limiter.release(token)

    @shared_task(bind=True, max_retries=3, default_retry_delay=60)
    def process_document_task(self, upload_id: str, user_id: int) -> None:
        """Run the full existing IDP pipeline asynchronously."""
        retries = self.request.retries
        logger.info(
            "OCR pipeline started — upload_id=%s user_id=%s retry=%d",
            upload_id,
            user_id,
            retries,
        )

        try:
            upload = OCRUpload.objects.select_related(
                "user"
            ).get(pk=upload_id)

            user = upload.user if upload.user_id == user_id else None

            if user is None:
                logger.error(
                    "User %s does not own upload %s.",
                    user_id,
                    upload_id,
                )
                return

            upload.status = OCRUpload.Status.PROCESSING
            upload.save(update_fields=["status"])

            result = idp_pipeline_service.process_upload(
                upload_id=upload_id,
                user=user,
            )

            logger.info(
                "OCR pipeline completed — upload_id=%s document=%s status=%s",
                upload_id,
                result.get("document_id"),
                result.get("status"),
            )

        except OCRUpload.DoesNotExist:
            logger.error(
                "OCR pipeline failed — upload not found — upload_id=%s",
                upload_id,
            )
            return

        except Exception as exc:
            logger.exception(
                "OCR pipeline failed — upload_id=%s retry=%d error=%s",
                upload_id,
                retries,
                exc,
            )
            raise self.retry(
                exc=exc,
                countdown=2 ** retries * 60,
            )

    @shared_task(bind=True, max_retries=3, default_retry_delay=60)
    def retry_stage_task(
        self,
        document_id: str,
        stage: str,
    ) -> None:
        """Re-run a single IDP pipeline stage."""
        try:
            document = OCRDocument.objects.get(pk=document_id)
        except OCRDocument.DoesNotExist:
            logger.error("Document %s not found.", document_id)
            return

        metadata = document.processing_metadata or {}
        retries = metadata.get("retry_count", 0) + 1
        metadata["retry_count"] = retries
        metadata["last_retried_stage"] = stage

        document.processing_metadata = metadata
        document.save(update_fields=["processing_metadata"])

        logger.info(
            "Retrying stage %s for document %s — attempt %d",
            stage,
            document_id,
            retries,
        )

    @shared_task
    def cleanup_task() -> None:
        """Clean up stale OCR uploads stuck in PROCESSING."""
        stale = OCRUpload.objects.filter(
            status=OCRUpload.Status.PROCESSING
        )
        updated = stale.update(status=OCRUpload.Status.FAILED)

        if updated:
            logger.info(
                "cleanup_task marked %d stale uploads as FAILED.",
                updated,
            )

except ImportError:  # pragma: no cover
    def process_test_ocr_upload_task(upload_id: str, user_id: str) -> None:
        logger.warning(
            "Celery not installed; running test OCR synchronously is unavailable."
        )

    def process_document_task(upload_id: str, user_id: int) -> None:
        logger.warning("Celery not installed; process_document_task is unavailable.")

    def retry_stage_task(document_id: str, stage: str) -> None:
        logger.warning("Celery not installed; retry_stage_task is unavailable.")

    def cleanup_task() -> None:
        logger.warning("Celery not installed; cleanup_task is unavailable.")
