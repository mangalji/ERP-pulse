"""
Database models for the OCR application.

It tracks the file through its lifecycle (UPLOADED → PROCESSING →
COMPLETED/FAILED) and stores the IDP engine entities (document, page,
version, quality metric) for the Enterprise IDP pipeline.
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
    processing_started_at = models.DateTimeField(null=True, blank=True)
    processing_completed_at = models.DateTimeField(null=True, blank=True)
    processing_duration_ms = models.PositiveIntegerField(null=True, blank=True)
    failure_reason = models.TextField(null=True, blank=True)

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
                condition=models.Q(file_size__gte=0),
                name='ocr_upload_file_size_non_negative',
            ),
        ]

    def __str__(self) -> str:
        return f'OCRUpload {self.id} ({self.original_filename})'


class DocumentType(models.TextChoices):
    """Supported business document types for the IDP engine."""

    INVOICE = 'INVOICE', 'Invoice'
    PURCHASE_ORDER = 'PURCHASE_ORDER', 'Purchase Order'
    SALES_ORDER = 'SALES_ORDER', 'Sales Order'
    CREDIT_NOTE = 'CREDIT_NOTE', 'Credit Note'
    DEBIT_NOTE = 'DEBIT_NOTE', 'Debit Note'
    RECEIPT = 'RECEIPT', 'Receipt'
    DELIVERY_CHALLAN = 'DELIVERY_CHALLAN', 'Delivery Challan'
    PACKING_LIST = 'PACKING_LIST', 'Packing List'
    UNKNOWN = 'UNKNOWN', 'Unknown'


class OCRDocumentStatus(models.TextChoices):
    """Lifecycle status of a processed IDP document."""

    UPLOADED = 'UPLOADED', 'Uploaded'
    VALIDATING = 'VALIDATING', 'Validating'
    CLASSIFYING = 'CLASSIFYING', 'Classifying'
    PROCESSING = 'PROCESSING', 'Processing'
    EXTRACTED = 'EXTRACTED', 'Extracted'
    REVIEW_REQUIRED = 'REVIEW_REQUIRED', 'Review Required'
    APPROVED = 'APPROVED', 'Approved'
    REJECTED = 'REJECTED', 'Rejected'
    READY_FOR_NETSUITE = 'READY_FOR_NETSUITE', 'Ready for NetSuite'
    FAILED = 'FAILED', 'Failed'


class OCRDocument(models.Model):
    """
    A business document processed through the IDP pipeline.

    This is the generic document-understanding record. Unlike
    ``OCRUpload`` (a raw file), ``OCRDocument`` carries the detected
    document type, lifecycle status, page count, version pointer,
    confidence, and processing metadata. It is the central entity the
    Document Review Workspace operates on.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    upload = models.OneToOneField(
        OCRUpload,
        on_delete=models.CASCADE,
        related_name='document',
        null=True,
        blank=True,
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='ocr_documents',
    )
    company = models.ForeignKey(
        'tenancy.Company',
        on_delete=models.CASCADE,
        related_name='ocr_documents',
        null=True,
        blank=True,
    )
    document_type = models.CharField(
        max_length=40,
        choices=DocumentType.choices,
        default=DocumentType.UNKNOWN,
        db_index=True,
    )
    status = models.CharField(
        max_length=30,
        choices=OCRDocumentStatus.choices,
        default=OCRDocumentStatus.UPLOADED,
        db_index=True,
    )
    page_count = models.PositiveIntegerField(default=0)
    current_version = models.PositiveIntegerField(default=0)
    overall_confidence = models.FloatField(null=True, blank=True)
    processing_started_at = models.DateTimeField(null=True, blank=True)
    processing_completed_at = models.DateTimeField(null=True, blank=True)
    processing_duration_ms = models.PositiveIntegerField(null=True, blank=True)
    failure_reason = models.TextField(null=True, blank=True)
    processing_metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text='Pipeline state: current_stage, retry_count, and stage timeline.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'ocr_document'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at'], name='ocr_doc_user_recent_idx'),
            models.Index(fields=['company', '-created_at'], name='ocr_doc_company_recent_idx'),
            models.Index(fields=['status'], name='ocr_doc_status_idx'),
            models.Index(fields=['document_type'], name='ocr_doc_type_idx'),
        ]

    def __str__(self) -> str:
        return f'OCRDocument {self.id} ({self.document_type})'


class OCRDocumentPage(models.Model):
    """
    A single page of a processed IDP document.

    Preserves page order, the rendered page image, the raw OCR text for
    that page, and the detected layout blocks (with bounding boxes when
    available).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(
        OCRDocument,
        on_delete=models.CASCADE,
        related_name='pages',
    )
    page_number = models.PositiveIntegerField()
    page_image = models.FileField(upload_to='ocr/pages/', null=True, blank=True)
    raw_text = models.TextField(blank=True, default='')
    layout_blocks = models.JSONField(default=dict, blank=True)
    is_blank = models.BooleanField(default=False)
    is_duplicate = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'ocr_document_page'
        ordering = ['page_number']
        constraints = [
            models.UniqueConstraint(
                fields=['document', 'page_number'],
                name='unique_document_page_number',
            ),
        ]

    def __str__(self) -> str:
        return f'{self.document_id} page {self.page_number}'


class OCRDocumentVersion(models.Model):
    """
    Immutable version snapshot of an IDP document.

    Stores the original document, processed document, raw OCR, normalized
    JSON, reviewed JSON, per-field confidence, validation errors, and the
    audit trail. Originals are never overwritten — each review/retry
    creates a new version.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(
        OCRDocument,
        on_delete=models.CASCADE,
        related_name='versions',
    )
    version_number = models.PositiveIntegerField()
    original_document = models.FileField(upload_to='ocr/versions/original/', null=True, blank=True)
    processed_document = models.FileField(upload_to='ocr/versions/processed/', null=True, blank=True)
    raw_ocr = models.JSONField(default=dict, blank=True)
    normalized_json = models.JSONField(default=dict, blank=True)
    reviewed_json = models.JSONField(default=dict, blank=True)
    confidence = models.JSONField(default=dict, blank=True)
    validation_errors = models.JSONField(default=list, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ocr_document_versions',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'ocr_document_version'
        ordering = ['version_number']
        constraints = [
            models.UniqueConstraint(
                fields=['document', 'version_number'],
                name='unique_document_version',
            ),
        ]

    def __str__(self) -> str:
        return f'{self.document_id} v{self.version_number}'


class OCRQualityMetric(models.Model):
    """
    Benchmark and quality metrics for the IDP engine.

    Captures per-document processing results used by the Quality
    Dashboard and benchmarking APIs. Aggregated later by document type
    and vendor for accuracy tracking.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    upload = models.ForeignKey(
        OCRUpload,
        on_delete=models.CASCADE,
        related_name='quality_metrics',
        null=True,
        blank=True,
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='ocr_quality_metrics',
    )
    company = models.ForeignKey(
        'tenancy.Company',
        on_delete=models.CASCADE,
        related_name='ocr_quality_metrics',
        null=True,
        blank=True,
    )
    document_type = models.CharField(max_length=40, default=DocumentType.UNKNOWN)
    vendor_name = models.CharField(max_length=255, blank=True, default='')
    processing_time_ms = models.PositiveIntegerField(default=0)
    overall_confidence = models.FloatField(default=0.0)
    success = models.BooleanField(default=False)
    failure_reason = models.CharField(max_length=255, blank=True, default='')
    validation_failures = models.PositiveIntegerField(default=0)
    ocr_accuracy = models.FloatField(default=0.0)
    extraction_accuracy = models.FloatField(default=0.0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'ocr_quality_metric'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at'], name='ocr_qm_user_recent_idx'),
            models.Index(fields=['company', '-created_at'], name='ocr_qm_company_recent_idx'),
            models.Index(fields=['document_type'], name='ocr_qm_type_idx'),
            models.Index(fields=['success'], name='ocr_qm_success_idx'),
        ]

    def __str__(self) -> str:
        return f'QualityMetric {self.id} ({self.document_type})'
