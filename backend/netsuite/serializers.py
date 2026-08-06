from rest_framework import serializers
from netsuite.models import NetSuiteConnection, EmployeeConnection
from django.utils import timezone
from django.core.validators import RegexValidator

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