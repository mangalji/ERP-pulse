"""
Serializers for the OCR application.

``UploadSerializer`` validates the incoming file (extension, size,
MIME type). ``UploadResponseSerializer`` shapes the response data
returned after a successful upload.
"""

from __future__ import annotations

from rest_framework import serializers

from ocr.exceptions import InvalidFileException
from ocr.validators import validate_extension, validate_file_size, validate_mime_type


class UploadSerializer(serializers.Serializer):
    """
    Validates the file field on POST /api/v1/ocr/upload/.

    Delegates extension, size, and MIME-type checks to the reusable
    validators in ``ocr.validators`` so the same rules can be applied
    outside the request/serializer context (e.g. in service-layer
    tests).
    """

    file = serializers.FileField()

    def validate_file(self, value):
        """
        Validate the uploaded file's extension, size, and MIME type.

        DRF calls this automatically for the ``file`` field. The method
        is named ``validate_<field_name>`` per DRF convention.

        ``InvalidFileException`` (a plain ``Exception`` subclass with a
        ``status_code`` attribute) is caught and re-raised as a DRF
        ``ValidationError`` so DRF includes it in
        ``serializer.errors`` instead of propagating it as an unhandled
        exception. The validators themselves stay framework-agnostic.
        """
        try:
            validate_extension(value.name)
            validate_file_size(value.size)
            validate_mime_type(value.content_type)
        except InvalidFileException as exc:
            raise serializers.ValidationError(str(exc)) from exc
        return value


class DocumentVersionSerializer(serializers.Serializer):
    """
    Serializes a single immutable version snapshot of a document.

    Used by the version history endpoints. Exposes the version number,
    normalized/reviewed JSON, confidence, validation errors, and the
    author + timestamp.
    """

    id = serializers.UUIDField()
    version_number = serializers.IntegerField()
    normalized_json = serializers.JSONField()
    reviewed_json = serializers.JSONField()
    confidence = serializers.JSONField()
    validation_errors = serializers.JSONField()
    created_by = serializers.CharField(source='created_by.email', default=None)
    created_at = serializers.DateTimeField()


class DocumentHistorySerializer(serializers.Serializer):
    """
    Serializes a document plus its ordered version history.

    Used by GET /documents/{id}/history/.
    """

    id = serializers.UUIDField()
    document_type = serializers.CharField()
    status = serializers.CharField()
    current_version = serializers.IntegerField()
    overall_confidence = serializers.FloatField(allow_null=True)
    processing_metadata = serializers.JSONField()
    versions = DocumentVersionSerializer(many=True)


class UploadResponseSerializer(serializers.Serializer):
    """
    Serializes the response data returned after a successful upload.

    Fields:
        upload_id:  UUID of the created ``OCRUpload`` record.
        status:     Lifecycle status (always ``UPLOADED`` in Phase 2).
        filename:   Original filename the user supplied.
        size:       File size in bytes.
        extension:  Canonical file extension (e.g. ``pdf``).
        file_hash:  SHA256 hash of the file content.
    """

    upload_id = serializers.UUIDField(source='id')
    status = serializers.CharField()
    filename = serializers.CharField(source='original_filename')
    size = serializers.IntegerField(source='file_size')
    extension = serializers.CharField()
    file_hash = serializers.CharField()

class OCRLineItemHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = __import__('ocr.models', fromlist=['OCRLineItem']).OCRLineItem
        fields = [
            'id',
            'line_number',
            'description',
            'quantity',
            'unit_price',
            'amount',
        ]


class OCRHistoryVersionSerializer(serializers.ModelSerializer):
    line_items = OCRLineItemHistorySerializer(many=True, read_only=True)

    class Meta:
        model = __import__('ocr.models', fromlist=['OCRDocumentVersion']).OCRDocumentVersion
        fields = [
            'id',
            'version_number',
            'invoice_number',
            'invoice_date',
            'due_date',
            'vendor_name',
            'customer_name',
            'subsidiary',
            'currency',
            'subtotal',
            'tax_amount',
            'tax_rate',
            'total_amount',
            'payment_terms',
            'line_items',
            'normalized_json',
            'created_at',
        ]


class OCRDocumentHistorySerializer(serializers.Serializer):
    id = serializers.UUIDField()
    upload_id = serializers.UUIDField(allow_null=True)
    filename = serializers.CharField(allow_null=True, allow_blank=True)
    document_type = serializers.CharField()
    status = serializers.CharField()
    current_version = serializers.IntegerField()
    overall_confidence = serializers.FloatField(allow_null=True)
    processing_metadata = serializers.JSONField()
    versions = OCRHistoryVersionSerializer(many=True)


class OCRHistoryListSerializer(serializers.Serializer):
    upload_id = serializers.UUIDField()
    document_id = serializers.UUIDField(allow_null=True)
    filename = serializers.CharField()
    status = serializers.CharField()
    document_type = serializers.CharField(allow_null=True, allow_blank=True)
    created_at = serializers.DateTimeField()
