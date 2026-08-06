"""
Invoice processing service.

Integrates with existing OCR and AI services without modifying them.
Pipeline: InvoiceFile → OCR extraction → Gemini extraction → store JSON.
"""

import logging
import time

from django.conf import settings
from django.db import transaction
from django.db.models import F

from invoice.models import InvoiceBatch, InvoiceFile, ExtractedInvoice, BatchStatus, FileStatus, ExtractionStatus
from ocr.models import OCRUpload
from ocr.services import ocr_service
from ocr.extraction_service import ocr_extraction_service

logger = logging.getLogger(__name__)


class InvoiceService:
    """Process invoice batches through OCR + AI extraction pipeline."""

    def process_batch(self, batch_id: str) -> None:
        """Process all files in a batch in the background."""
        try:
            batch = InvoiceBatch.objects.get(id=batch_id)
        except InvoiceBatch.DoesNotExist:
            logger.error('Batch %s not found.', batch_id)
            return

        batch.status = BatchStatus.PROCESSING
        batch.save()

        files = list(batch.files.all())
        for invoice_file in files:
            self._process_file(invoice_file)

        # Update batch status
        batch.refresh_from_db()
        if batch.failed_files == 0:
            batch.status = BatchStatus.COMPLETED
        elif batch.processed_files == 0:
            batch.status = BatchStatus.FAILED
        else:
            batch.status = BatchStatus.COMPLETED  # partial success
        batch.save()

    def _process_file(self, invoice_file: InvoiceFile) -> None:
        """Process a single invoice file through the pipeline."""
        start_time = time.perf_counter()
        
        try:
            invoice_file.status = FileStatus.PROCESSING
            invoice_file.save()

            # Step 1: Upload to OCR service (creates OCRUpload record)
            ocr_upload = ocr_service.upload(
                file=invoice_file.uploaded_file,
                user=invoice_file.batch.uploaded_by,
            )

            # Step 2: Run OCR extraction pipeline (image preprocessing + Gemini)
            extraction_result = ocr_extraction_service.extract(
                upload=ocr_upload,
                user=invoice_file.batch.uploaded_by,
            )

            # Step 3: Normalize and store result
            extracted_data = extraction_result.get('data', {})
            confidence = extraction_result.get('confidence', {}).get('overall', 0.0)
            
            ExtractedInvoice.objects.create(
                invoice_file=invoice_file,
                extracted_json=extracted_data,
                confidence_score=confidence,
                extraction_status=ExtractionStatus.COMPLETED,
            )

            invoice_file.status = FileStatus.EXTRACTED
            invoice_file.processing_time = time.perf_counter() - start_time
            invoice_file.save()

            InvoiceBatch.objects.filter(id=invoice_file.batch.id).update(processed_files=F('processed_files') + 1)

        except Exception as exc:
            logger.exception('Failed to process file %s: %s', invoice_file.id, exc)
            invoice_file.status = FileStatus.FAILED
            invoice_file.processing_time = time.perf_counter() - start_time
            invoice_file.save()
            InvoiceBatch.objects.filter(id=invoice_file.batch.id).update(failed_files=F('failed_files') + 1)

    def retry_file(self, file_id: str) -> None:
        """
        Retry processing for a failed file.
        
        Resets file status to PROCESSING and re-runs the pipeline.
        """
        try:
            invoice_file = InvoiceFile.objects.get(id=file_id)
        except InvoiceFile.DoesNotExist:
            logger.error('File %s not found for retry.', file_id)
            return

        if invoice_file.status == FileStatus.PROCESSING:
            logger.warning('File %s is already processing.', file_id)
            return

        # Reset batch counters
        batch = invoice_file.batch
        if invoice_file.status == FileStatus.FAILED:
            InvoiceBatch.objects.filter(id=batch.id).update(failed_files=F('failed_files') - 1)

        # Re-process
        self._process_file(invoice_file)


# Module-level singleton
invoice_service = InvoiceService()


def start_background_processing(batch_id: str) -> None:
    """
    Start batch processing via Celery.
    
    Returns immediately; Celery worker processes the batch asynchronously.
    """
    from invoice.tasks import process_batch_task
    process_batch_task.delay(batch_id)