from __future__ import annotations
from django.contrib import admin
from ocr.models import OCRUpload

# Register your models here.
"""
Django admin configuration for the OCR application.

Registers ``OCRUpload`` with a list display that shows the key fields
an admin needs to triage uploads: user, filename, status, hash, and
timestamps. Filtering by status and searching by filename/hash are
enabled for quick lookup.
"""


@admin.register(OCRUpload)
class OCRUploadAdmin(admin.ModelAdmin):
    """Admin interface for the ``OCRUpload`` model."""
    list_display = (
        'id',
        'user',
        'original_filename',
        'extension',
        'file_size',
        'status',
        'file_hash',
        'created_at',
    )
    list_filter = ('status','extension','created_at')
    search_fields = (
        'original_filename',
        'stored_filename',
        'file_hash',
        'user_email',
    )
    readonly_fields = (
        'id','stored_filename','file_hash','file_size','mime_type','extension','created_at','updated_at',
    )
    ordering = ('-created_at',)