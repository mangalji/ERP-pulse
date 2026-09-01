from __future__ import annotations

from rest_framework import serializers

from ocr.exceptions import InvalidFileException, UnsupportedFormatException
# from ocr.models import OCRBatch, OCRUpload
from ocr.validators import validate_extension, validate_file_size, validate_mime_type
from ocr.formats import lookup_format


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
            fmt = lookup_format(
                extension=value.name.rsplit('.', 1)[-1].lower(),
                mime_type=value.content_type or '',
            )
            validate_file_size(value.size, max_size=fmt.max_file_size_mb * 1024 * 1024)
            validate_mime_type(value.content_type)
        except InvalidFileException as exc:
            raise serializers.ValidationError(str(exc)) from exc
        except UnsupportedFormatException:
            raise
        return value


class OCRSaveRequestSerializer(serializers.Serializer):
    """
    Save user-reviewed OCR data.

    Exactly one target is required:
    - upload_id: for a freshly extracted result that has not yet been saved.
    - document_id: for an existing saved OCR document.
    """

    upload_id = serializers.UUIDField(required=False, allow_null=True)
    document_id = serializers.UUIDField(required=False, allow_null=True)
    data = serializers.JSONField()

    def validate(self, attrs):
        upload_id = attrs.get('upload_id')
        document_id = attrs.get('document_id')

        if bool(upload_id) == bool(document_id):
            raise serializers.ValidationError(
                "Provide exactly one of upload_id or document_id."
            )
        
        if not isinstance(attrs.get('data'), dict):
            raise serializers.ValidationError("Data must be a JSON object.")

        return attrs

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
    requested_fields = serializers.JSONField(allow_null=True)
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

class OCRBatchHistoryItemSerializer(serializers.Serializer):
    upload_id = serializers.UUIDField()
    filename = serializers.CharField()
    status = serializers.CharField()
    document_id = serializers.UUIDField(allow_null=True)
    created_at = serializers.DateTimeField()

class OCRHistoryFileSerializer(serializers.Serializer):
    """One file entry exposed from a single file or an OCR batch."""

    upload_id = serializers.UUIDField()
    document_id = serializers.UUIDField(allow_null=True)
    version_id = serializers.UUIDField(allow_null=True)
    version_number = serializers.IntegerField(allow_null=True)
    filename = serializers.CharField()
    status = serializers.CharField()
    data = serializers.JSONField(allow_null=True)
    error = serializers.CharField(allow_null=True, allow_blank=True)


class OCRHistoryEntrySerializer(serializers.Serializer):
    """One top-level entry in the user's/company admin history."""

    type = serializers.ChoiceField(choices=("single", "batch"))
    batch_id = serializers.UUIDField(allow_null=True)
    document_id = serializers.UUIDField(allow_null=True)
    upload_id = serializers.UUIDField(allow_null=True)
    filename = serializers.CharField(allow_null=True, allow_blank=True)
    file_count = serializers.IntegerField()
    status = serializers.CharField()
    source_type = serializers.CharField(allow_null=True, allow_blank=True)
    created_at = serializers.DateTimeField()
    owner_id = serializers.CharField(allow_null=True, allow_blank=True)
    owner_name = serializers.CharField(allow_null=True, allow_blank=True)
    validation_status = serializers.CharField(allow_null=True, allow_blank=True)
    validation_errors = serializers.ListField(allow_null=True, required=False)
    validation_id = serializers.UUIDField(allow_null=True, required=False)
    validation_updated_at = serializers.DateTimeField(allow_null=True, required=False)



class OCRBatchHistorySerializer(serializers.Serializer):
    """Detailed view of one OCR batch."""

    batch_id = serializers.UUIDField()
    status = serializers.CharField()
    source_type = serializers.CharField()
    source_filename = serializers.CharField(allow_null=True, allow_blank=True)
    created_at = serializers.DateTimeField()
    started_at = serializers.DateTimeField(allow_null=True)
    completed_at = serializers.DateTimeField(allow_null=True)
    total_files = serializers.IntegerField()
    queued_files = serializers.IntegerField()
    processing_files = serializers.IntegerField()
    completed_files = serializers.IntegerField()
    failed_files = serializers.IntegerField()
    owner_id = serializers.CharField(allow_null=True, allow_blank=True)
    owner_name = serializers.CharField(allow_null=True, allow_blank=True)
    files = OCRHistoryFileSerializer(many=True)

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


class OCRExtractionTemplateSerializer(serializers.ModelSerializer):
    """Read/write representation of a saved dynamic extraction template."""

    class Meta:
        model = __import__('ocr.models', fromlist=['OCRExtractionTemplate']).OCRExtractionTemplate
        fields = [
            'id',
            'name',
            'fields_config',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class OCRExtractionTemplateCreateSerializer(serializers.Serializer):
    """
    Create/update payload for an extraction template.

    ``fields_config`` uses the same shape as ``OCRBatch.requested_fields_json``:
    {"standard_fields": [...], "custom_fields": [{...}]}.
    """

    name = serializers.CharField(max_length=150)
    fields_config = serializers.JSONField(required=False, default=dict)

    def validate_fields_config(self, value):
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise serializers.ValidationError(
                "fields_config must be a JSON object."
            )
        # Route through the canonical resolver so the Phase 2 line-custom
        # field rule and shape validation are enforced on save too.
        from ocr.notebook_extraction_service import resolve_field_config

        try:
            resolve_field_config(value)
        except ValueError as exc:
            raise serializers.ValidationError(str(exc)) from exc
        return value

    def validate(self, attrs):
        if not attrs.get('name', '').strip():
            raise serializers.ValidationError(
                {"name": "Template name is required."}
            )
        return attrs
