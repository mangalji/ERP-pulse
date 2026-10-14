from rest_framework import serializers
from netsuite.models import NetSuiteConnection, EmployeeConnection, NetSuiteCustomField
from django.utils import timezone
from django.core.validators import RegexValidator
from ocr.models import OCRNetSuiteFieldMapping, OCRValidationResult, MappingStatus
from urllib.parse import urlsplit, urlunsplit
from django.conf import settings

# NetSuite account IDs are alphanumeric plus underscore (e.g. "TD1234567") — see netsuite/oauth.py's
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
    callback_uri = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=500,
    )

    def validate_callback_uri(self, value):
        value = (value or "").strip()

        if not value:
            return None

        if any(character.isspace() for character in value):
            raise serializers.ValidationError(
                "Spaces in redirect URLs must be URL-encoded."
            )

        if value.startswith("//"):
            raise serializers.ValidationError(
                "Enter a full URL or an application-relative path, "
                "not a protocol-relative URL."
            )

        if value.startswith("/"):
            frontend_url = str(getattr(settings, "FRONTEND_URL", "") or "")
            frontend = urlsplit(frontend_url)


            if frontend.scheme not in ("http", "https") or not frontend.netloc:
                raise serializers.ValidationError(
                    "The frontend base URL is not configured correctly."
                )

            relative = urlsplit(value)
            value = urlunsplit((
                frontend.scheme,
                frontend.netloc,
                relative.path,
                relative.query,
                relative.fragment,
            ))
        elif not value.lower().startswith(("http://", "https://")):
            value = f"https://{value}"

        try:
            parsed = urlsplit(value)
            hostname = parsed.hostname
            _ = parsed.port
        except ValueError as exc:
            raise serializers.ValidationError(
                "Enter a valid redirect URL."
            ) from exc

        if (
            parsed.scheme.lower() not in ("http", "https")
            or not parsed.netloc
            or not hostname
            or parsed.username is not None
            or parsed.password is not None
        ):
            raise serializers.ValidationError(
                "Enter a valid HTTP or HTTPS redirect URL."
            )

        return value


class EmployeeConnectionSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.get_full_name', read_only=True)
    employee_email = serializers.CharField(source='employee.email', read_only=True)

    class Meta:
        model = EmployeeConnection
        fields = ('id', 'employee', 'employee_name', 'employee_email', 'connection', 'created_at')


class NetSuiteConnectionListSerializer(serializers.ModelSerializer):
    token_expires_in_seconds = serializers.SerializerMethodField()
    reauth_required_by = serializers.DateTimeField(
        source="refresh_token_expires_at", read_only=True
    )
    needs_reauth = serializers.SerializerMethodField()
    health = serializers.ReadOnlyField()
    company_name = serializers.CharField(source='company.name', read_only=True)
    employee_assignments = EmployeeConnectionSerializer(
        many=True,
        read_only=True,
    )

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
            "reauth_required_by",
            "needs_reauth",
            "company",
            "company_name",
            "employee_assignments",
        )

    def get_needs_reauth(self, obj):
        if obj.status == "error" and not obj.refresh_token:
            return True
        deadline = obj.refresh_token_expires_at
        return bool(deadline and deadline <= timezone.now())

    def get_token_expires_in_seconds(self, obj):
        if not obj.access_token_expires_at:
            return None

        remaining = (obj.access_token_expires_at - timezone.now()).total_seconds()
        return max(int(remaining), 0)

class NetSuiteConnectionRenameSerializer(serializers.Serializer):
    client_name = serializers.CharField(max_length=255)

class AssignEmployeeSerializer(serializers.Serializer):
    employee_id = serializers.UUIDField()

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
        

class SaveMappingRequestSerializer(serializers.Serializer):
    connection_id = serializers.UUIDField()
    record_type = serializers.CharField(default='vendorBill',max_length=64)
    mappings = serializers.ListField(
        child=serializers.DictField(),
        allow_empty=False,
    )


class ValidateDocumentRequestSerializer(serializers.Serializer):
    document_id = serializers.UUIDField()
    connection_id = serializers.UUIDField()
