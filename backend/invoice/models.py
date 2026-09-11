"""
Invoice module models.

This module provides the schema for batch invoice processing:
- InvoiceBatch: groups files uploaded together
- InvoiceFile: a single uploaded file
"""

from django.conf import settings
from django.db import models

from tenancy.models import Company


class BatchStatus(models.TextChoices):
    UPLOADING = 'UPLOADING', 'Uploading'
    PROCESSING = 'PROCESSING', 'Processing'
    COMPLETED = 'COMPLETED', 'Completed'
    FAILED = 'FAILED', 'Failed'


class FileStatus(models.TextChoices):
    UPLOADED = 'UPLOADED', 'Uploaded'
    PROCESSING = 'PROCESSING', 'Processing'
    EXTRACTED = 'EXTRACTED', 'Extracted'
    REVIEW_REQUIRED = 'REVIEW_REQUIRED', 'Review Required'
    APPROVED = 'APPROVED', 'Approved'
    REJECTED = 'REJECTED', 'Rejected'
    READY_FOR_NETSUITE = 'READY_FOR_NETSUITE', 'Ready for NetSuite'
    FAILED = 'FAILED', 'Failed'

class InvoiceBatch(models.Model):
    """Batch of invoice files uploaded together."""

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='invoice_batches')
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='invoice_batches',
    )
    total_files = models.PositiveIntegerField(default=0)
    processed_files = models.PositiveIntegerField(default=0)
    failed_files = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, choices=BatchStatus.choices, default=BatchStatus.UPLOADING)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'invoice_batch'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', '-created_at'], name='inv_batch_company_recent_idx'),
        ]

    def __str__(self) -> str:
        return f'Batch #{self.id} — {self.company.name}'


class InvoiceFile(models.Model):
    """A single uploaded invoice file."""

    batch = models.ForeignKey(InvoiceBatch, on_delete=models.CASCADE, related_name='files')
    uploaded_file = models.FileField(upload_to='invoices/%Y/%m/%d/')
    original_filename = models.CharField(max_length=255)
    file_type = models.CharField(max_length=20)
    file_size = models.BigIntegerField()
    status = models.CharField(max_length=20, choices=FileStatus.choices, default=FileStatus.UPLOADED)
    processing_time = models.FloatField(null=True, blank=True, help_text='Processing time in seconds')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'invoice_file'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['batch', '-created_at'], name='invoice_file_batch_recent_idx'),
            models.Index(fields=['status'], name='invoice_file_status_idx'),
        ]

    def __str__(self) -> str:
        return f'{self.original_filename} ({self.batch_id})'
