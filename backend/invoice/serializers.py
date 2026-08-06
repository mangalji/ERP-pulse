"""
Serializers for the invoice module.
"""

from rest_framework import serializers

from invoice.models import (
    ExtractedInvoice,
    InvoiceBatch,
    InvoiceFile,
    InvoiceReviewHistory,
    InvoiceNetSuiteMapping,
    FileStatus,
)
from invoice.validators import InvoiceValidator


class InvoiceReviewHistorySerializer(serializers.ModelSerializer):
    edited_by_name = serializers.CharField(source='edited_by.get_full_name', read_only=True)

    class Meta:
        model = InvoiceReviewHistory
        fields = ['id', 'field', 'old_value', 'new_value', 'edited_by', 'edited_by_name', 'edited_at']
        read_only_fields = ['id', 'edited_at']


class ExtractedInvoiceSerializer(serializers.ModelSerializer):
    review_history = InvoiceReviewHistorySerializer(many=True, read_only=True)
    validation_errors = serializers.SerializerMethodField()

    class Meta:
        model = ExtractedInvoice
        fields = [
            'id', 'invoice_file', 'extracted_json', 'confidence_score',
            'extraction_status', 'reviewed_by', 'reviewed_at',
            'created_at', 'review_history', 'validation_errors',
        ]
        read_only_fields = ['id', 'created_at']

    def get_validation_errors(self, obj):
        validator = InvoiceValidator()
        errors = validator.validate(obj.extracted_json)
        return [e.to_dict() for e in errors]


class InvoiceNetSuiteMappingSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceNetSuiteMapping
        fields = ['id', 'invoice_field', 'netsuite_field', 'is_required', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class InvoiceFileSerializer(serializers.ModelSerializer):
    extraction = ExtractedInvoiceSerializer(read_only=True)

    class Meta:
        model = InvoiceFile
        fields = [
            'id', 'batch', 'uploaded_file', 'original_filename',
            'file_type', 'file_size', 'status', 'processing_time', 'created_at', 'extraction',
        ]
        read_only_fields = ['id', 'status', 'processing_time', 'created_at']


class InvoiceBatchSerializer(serializers.ModelSerializer):
    files = InvoiceFileSerializer(many=True, read_only=True)
    progress = serializers.SerializerMethodField()
    extracted_data = serializers.SerializerMethodField()

    class Meta:
        model = InvoiceBatch
        fields = [
            'id', 'company', 'uploaded_by', 'total_files',
            'processed_files', 'failed_files', 'status',
            'created_at', 'files', 'progress', 'extracted_data',
        ]
        read_only_fields = ['id', 'company', 'uploaded_by', 'created_at']

    def get_progress(self, obj):
        if obj.total_files == 0:
            return 0
        return round((obj.processed_files / obj.total_files) * 100, 1)

    def get_extracted_data(self, obj):
        data = []
        for invoice_file in obj.files.filter(status__in=[FileStatus.EXTRACTED, FileStatus.APPROVED, FileStatus.READY_FOR_NETSUITE]).select_related('extraction'):
            extraction = getattr(invoice_file, 'extraction', None)
            if extraction:
                data.append({
                    'file_id': str(invoice_file.id),
                    'filename': invoice_file.original_filename,
                    'extracted_json': extraction.extracted_json,
                    'confidence_score': extraction.confidence_score,
                    'extraction_status': extraction.extraction_status,
                })
        return data