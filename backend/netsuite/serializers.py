from rest_framework import serializers
from netsuite.models import NetSuiteConnection
from django.utils import timezone

class NetSuiteCallbackSerializer(serializers.Serializer):
    """
    Validates the query parameters NetSuite appends to the redirect URI
    after the user approves or denies access on the consent screen.

    `code` and `error` are mutually exclusive in practice (NetSuite sends
    one or the other), so both stay optional here; the view decides which
    case it is and raises the appropriate domain exception.
    """

    state = serializers.CharField()
    code = serializers.CharField(required=False)
    error = serializers.CharField(required=False)

class NetSuiteConnectionCreateSerializer(serializers.Serializer):
    client_name= serializers.CharField(max_length=255)
    environment = serializers.ChoiceField(
        choices=["sandbox","production"]
    )
    client_id = serializers.CharField()
    client_secret = serializers.CharField()
    netsuite_account_id = serializers.CharField()

class NetSuiteConnectionListSerializer(serializers.ModelSerializer):
    token_expires_in_seconds = serializers.SerializerMethodField()

    class Meta:
        model = NetSuiteConnection
        fields = (
            "id",
            "client_name",
            "environment",
            "netsuite_account_id",
            "status",
            "is_active",
            "connected_at",
            "last_synced_at",
            "last_error",
            "consecutive_failures",
            "token_expires_in_seconds",
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