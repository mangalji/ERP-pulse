from rest_framework import serializers
from netsuite.models import NetSuiteConnection, EmployeeConnection, NetSuiteCustomField
from django.utils import timezone
from django.core.validators import RegexValidator
from ocr.models import OCRNetSuiteFieldMapping, OCRValidationResult, MappingStatus

# NetSuite account IDs are alphanumeric plus underscore (e.g. "1234567",
# "1234567_SB1", "TD1234567") — see netsuite/oauth.py's
# netsuite_account_domain() for the exact transformation applied to this
# value. Anything outside that character set can never be a real
# NetSuite account id.
netsuite_account_id_validator = RegexValidator(
    regex=r'^[A-Za-z0-9_]+$',
    message='NetSuite Account ID may only contain letters, numbers, and underscores.',
)

class NetSuiteCallbackSerializer(serializers.Serializer):
    """
    Validates the query parameters NetSuite appends to the redirect URI
    after the user approves or denies access on the consent screen.

    `code` and `error` are mutually exclusive in practice (NetSuite sends
    one or the other), so both stay optional here; the view decides which
    case it is and raises the appropriate domain exception.
    """

    state = serializers.CharField(max_length=2048)
    code = serializers.CharField(required=False, max_length=1024)
    error = serializers.CharField(required=False,max_length=512)

class NetSuiteConnectionCreateSerializer(serializers.Serializer):
    client_name= serializers.CharField(max_length=255)
    environment = serializers.ChoiceField(
        choices=["sandbox","production"]
    )
    client_id = serializers.CharField(min_length=1, max_length=500)
    client_secret = serializers.CharField(min_length=1, max_length=500)
    netsuite_account_id = serializers.CharField(
        min_length=1, max_length=20, validators=[netsuite_account_id_validator],
    )

class NetSuiteConnectionListSerializer(serializers.ModelSerializer):
    token_expires_in_seconds = serializers.SerializerMethodField()
    health = serializers.ReadOnlyField()
    company_name = serializers.CharField(source='company.name', read_only=True)

    class Meta:
        model = NetSuiteConnection
        fields = (
            "id",
            "client_name",
            "environment",
            "netsuite_account_id",
            "status",
            "is_active",
            "health",
            "connected_at",
            "last_synced_at",
            "last_used_at",
            "last_error",
            "consecutive_failures",
            "token_expires_in_seconds",
            "company",
            "company_name",
        )

    def get_token_expires_in_seconds(self, obj):
        if not obj.access_token_expires_at:
            return None

        remaining = (obj.access_token_expires_at - timezone.now()).total_seconds()
        return max(int(remaining), 0)

class NetSuiteConnectionRenameSerializer(serializers.Serializer):
    client_name = serializers.CharField(max_length=255)

class NetSuiteConnectionSwitchSerializer(serializers.Serializer):
    pass


class EmployeeConnectionSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.get_full_name', read_only=True)
    employee_email = serializers.CharField(source='employee.email', read_only=True)

    class Meta:
        model = EmployeeConnection
        fields = ('id', 'employee', 'employee_name', 'employee_email', 'connection', 'created_at')


class AssignEmployeeSerializer(serializers.Serializer):
    employee_id = serializers.UUIDField()


class NetSuiteConnectionTestSerializer(serializers.Serializer):
    connection_id = serializers.UUIDField()


class OCRNetSuiteFieldMappingSerializer(serializers.ModelSerializer):
    class Meta:
        model = OCRNetSuiteFieldMapping
        fields = (
            'id',
            'company',
            'connection',
            'record_type',
            'source_field_key',
            'source_field_label',
            'source_scope',
            'source_datatype',
            'target_field_id',
            'target_field_label',
            'target_scope',
            'target_datatype',
            'is_required',
            'is_custom',
            'reference_type',
            'mapping_status',
            'confidence',
            'metadata',
            'created_at',
            'updated_at',
        )
        read_only_fields = (
            'id',
            'company',
            'created_at',
            'updated_at',
        )


class OCRValidationResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = OCRValidationResult
        fields = (
            'id',
            'document',
            'version',
            'connection',
            'status',
            'vendor_extracted_name',
            'vendor_matched',
            'vendor_netsuite_id',
            'items',
            'errors',
            'created_at',
            'updated_at',
        )
        read_only_fields = ('id', 'created_at', 'updated_at')


class NetSuiteCustomFieldSerializer(serializers.ModelSerializer):
    class Meta:
        model = NetSuiteCustomField
        fields = (
            'id',
            'company',
            'connection',
            'record_type',
            'scope',
            'field_label',
            'field_id',
            'datatype',
            'source_field_key',
            'source_field_label',
            'netsuite_field_id',
            'status',
            'error',
            'created_at',
            'updated_at',
        )
        read_only_fields = (
            'id',
            'company',
            'created_at',
            'updated_at',
        )


class NetSuiteFieldCatalogueSerializer(serializers.Serializer):
    record_type = serializers.CharField()
    # body_fields = serializers.ListField(
    #     child=serializers.DictField(),
    #     allow_empty=True,
    # )
    # line_fields = serializers.ListField(
    #     child=serializers.DictField(),
    #     allow_empty=True,
    # )
    fields = serializers.DictField()
    custom_fields = serializers.ListField(
        child=serializers.DictField(),
        allow_empty=True,
    )


class MappingSourceFieldSerializer(serializers.Serializer):
    key = serializers.CharField(required=False, allow_blank=False, max_length=150)
    field_key = serializers.CharField(required=False, allow_blank=False, max_length=150)
    label = serializers.CharField(required=False, allow_blank=True, max_length=255)
    field_label = serializers.CharField(required=False, allow_blank=True, max_length=255)
    scope = serializers.ChoiceField(
        choices=('header', 'line'),
        default='header',
    )
    datatype = serializers.ChoiceField(
        choices=('text', 'number', 'date', 'boolean', 'currency'),
        default='text',
    )

    def validate(self, attrs):
        key = attrs.get('key') or attrs.get('field_key')
        if not key:
            raise serializers.ValidationError(
                {'key': 'Either key or field_key is required.'}
            )

        label = attrs.get('label')
        if label is None or not label.strip():
            label = attrs.get('field_label') or key

        attrs['key'] = key
        attrs['label'] = label.strip()
        return attrs


class MappingSuggestionRequestSerializer(serializers.Serializer):
    connection_id = serializers.UUIDField()
    record_type = serializers.CharField(
        max_length=64,
        default='vendorBill',
    )
    source_fields = MappingSourceFieldSerializer(
        many=True,
        allow_empty=False,
    )


class MappingSuggestionSerializer(serializers.Serializer):
    source_field_key = serializers.CharField()
    source_field_label = serializers.CharField()
    source_scope = serializers.ChoiceField(
        choices=('header', 'line'),
    )
    source_datatype = serializers.CharField()
    status = serializers.ChoiceField(
        choices=[c[0] for c in MappingStatus.choices],
    )
    suggested_target = serializers.DictField(
        required=False,
        allow_null=True,
    )
    candidates = serializers.ListField(
        child=serializers.DictField(),
    )


class MappingSaveItemSerializer(serializers.Serializer):
    source_field_key = serializers.CharField(
        max_length=150,
        allow_blank=False,
    )
    source_field_label = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=True,
    )
    source_scope = serializers.ChoiceField(
        choices=('header', 'line'),
        default='header',
    )
    source_datatype = serializers.ChoiceField(
        choices=('text', 'number', 'date', 'boolean', 'currency'),
        default='text',
    )
    target_field_id = serializers.CharField(
        max_length=150,
        allow_blank=True,
        required=False,
        default='',
    )
    mapping_status = serializers.ChoiceField(
        choices=[c[0] for c in MappingStatus.choices],
        required=False,
    )
    confidence = serializers.FloatField(
        required=False,
        allow_null=True,
        min_value=0,
        max_value=1,
    )
    metadata = serializers.DictField(
        required=False,
        default=dict,
    )


class SaveMappingRequestSerializer(serializers.Serializer):
    connection_id = serializers.UUIDField()
    record_type = serializers.CharField(
        max_length=64,
        default='vendorBill',
    )
    mappings = MappingSaveItemSerializer(
        many=True,
        allow_empty=False,
    )


class ValidateDocumentRequestSerializer(serializers.Serializer):
    document_id = serializers.UUIDField()


class CreateCustomFieldRequestSerializer(serializers.Serializer):
    connection_id = serializers.UUIDField()
    record_type = serializers.CharField(
        max_length=64,
        default='vendorBill',
    )
    scope = serializers.ChoiceField(
        choices=[c[0] for c in NetSuiteCustomField.SCOPE_CHOICES],
    )
    field_label = serializers.CharField(max_length=255)
    datatype = serializers.ChoiceField(
        choices=[c[0] for c in NetSuiteCustomField.DATATYPE_CHOICES],
    )
    source_field_key = serializers.CharField(max_length=100)
    source_field_label = serializers.CharField(max_length=255)