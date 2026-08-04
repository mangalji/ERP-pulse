"""
Database models for the OCR application.

It tracks the file through its lifecycle (UPLOADED → PROCESSING →
COMPLETED/FAILED) and stores metadata for duplicate detection, audit,
and performance analysis.
"""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models


class OCRUpload(models.Model):
    """
    A single file uploaded for OCR processing.

     The model stores both the original metadata (filename, size, MIME
    type, extension, SHA256 hash) and the on-disk reference (``file``
    field) so the pipeline can trace any upload back to its source.

    The ``file_hash`` field enables duplicate detection — two uploads
    with identical content will share the same hash, allowing a future
    optimisation to skip re-processing.

    Processing metadata (``processing_started_at``,
    ``processing_completed_at``, ``processing_duration_ms``) is
    populated by later phases when the extraction pipeline runs.
    ``failure_reason`` captures the error message if processing fails.
    """

    class Status(models.TextChoices):
        UPLOADED = 'UPLOADED', 'Uploaded'
        PROCESSING = 'PROCESSING', 'Processing'
        COMPLETED = 'COMPLETED', 'Completed'
        FAILED = 'FAILED', 'Failed'

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='ocr_uploads',
    )

    original_filename = models.CharField(max_length=255)
    stored_filename = models.CharField(max_length=255)
    file = models.FileField(upload_to='ocr/')
    file_size = models.PositiveBigIntegerField()
    mime_type = models.CharField(max_length=100)
    extension = models.CharField(max_length=10)
    file_hash = models.CharField(
        max_length=64,
        help_text='SHA256 hash of the file content for duplicate detection.',
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.UPLOADED,
        db_index=True,
    )
    processing_started_at = models.DateTimeField(null=True,blank=True)
    processing_completed_at = models.DateTimeField(null=True,blank=True)
    processing_duration_ms = models.PositiveIntegerField(null=True,blank=True)
    failure_session = models.TextField(null=True,blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'ocr_upload'
        ordering = ['-created_at']
        indexes = [
            models.Index(
                fields=['user', '-created_at'],
                name='ocr_upload_user_recent_idx',
            ),
            models.Index(
                fields=['file_hash'],
                name='ocr_upload_file_hash_idx',
            ),
            models.Index(
                fields=['status'],
                name='ocr_upload_status_idx',
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition = models.Q(file_size__gte=0),
                name = 'ocr_upload_file_size_non_negative',
                
            )
        ]

    def __str__(self) -> str:
        return f'OCRUpload {self.id} ({self.original_filename})'