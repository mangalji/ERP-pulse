"""
Invoice processing tasks.

Uses Celery if available; otherwise falls back to no-op so the module
can be imported without celery installed.
"""

import logging

from django.db import transaction
from django.db.models import F

from invoice.models import InvoiceBatch, InvoiceFile, BatchStatus, FileStatus
from invoice.services import invoice_service

logger = logging.getLogger(__name__)

try:
    from celery import shared_task

    @shared_task(bind=True, max_retries=3, default_retry_delay=60)
    def process_batch_task(self, batch_id: str) -> None:
        try:
            batch = InvoiceBatch.objects.get(id=batch_id)
        except InvoiceBatch.DoesNotExist:
            logger.error('Batch %s not found.', batch_id)
            return

        batch.status = BatchStatus.PROCESSING
        batch.save()

        files = list(batch.files.all())
        for invoice_file in files:
            try:
                invoice_service._process_file(invoice_file)
            except Exception as exc:
                logger.exception('Failed to process file %s: %s', invoice_file.id, exc)
                raise self.retry(exc=exc, countdown=2 ** self.request.retries * 60)

        batch.refresh_from_db()
        if batch.failed_files == 0:
            batch.status = BatchStatus.COMPLETED
        elif batch.processed_files == 0:
            batch.status = BatchStatus.FAILED
        else:
            batch.status = BatchStatus.COMPLETED
        batch.save()

    @shared_task(bind=True, max_retries=3, default_retry_delay=60)
    def process_invoice_file_task(self, file_id: str) -> None:
        try:
            invoice_file = InvoiceFile.objects.get(id=file_id)
        except InvoiceFile.DoesNotExist:
            logger.error('File %s not found.', file_id)
            return

        try:
            invoice_service._process_file(invoice_file)
        except Exception as exc:
            logger.exception('Failed to process file %s: %s', file_id, exc)
            raise self.retry(exc=exc, countdown=2 ** self.request.retries * 60)

except ImportError:
    # Celery not installed — define no-op placeholders so imports still work
    def process_batch_task(batch_id: str) -> None:  # type: ignore[misc]
        logger.warning('Celery not installed; process_batch_task is a no-op.')

    def process_invoice_file_task(file_id: str) -> None:  # type: ignore[misc]
        logger.warning('Celery not installed; process_invoice_file_task is a no-op.')