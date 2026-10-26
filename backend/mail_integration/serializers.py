from django.utils import timezone
from rest_framework import serializers

from mail_integration.models import EmailIntegration


class EmailIntegrationCreateSerializer(serializers.Serializer):
    provider = serializers.ChoiceField(choices=EmailIntegration.Provider.choices)
    mailbox_email = serializers.EmailField()
    display_name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    client_id = serializers.CharField(max_length=255, required=False, write_only=True, trim_whitespace=True)
    client_secret = serializers.CharField(required=False, write_only=True, trim_whitespace=True)
    ocr_template_id = serializers.UUIDField(required=False, allow_null=True)
    zoho_data_center = serializers.ChoiceField(
        choices=["COM", "IN", "EU", "COM_AU", "JP", "CA", "COM_CN", "AE", "SA"],
        required=False,
    )

    def validate_ocr_template_id(self, value):
        if value is None:
            return value
        from ocr.models import OCRExtractionTemplate
        request = self.context.get("request")
        if request is None or not OCRExtractionTemplate.objects.filter(id=value, company=request.user.company).exists():
            raise serializers.ValidationError("OCR extraction template not found.")
        return value

    def validate(self, attrs):
        if bool(attrs.get("client_id")) != bool(attrs.get("client_secret")):
            raise serializers.ValidationError("Provide both Client ID and Client Secret.")
        if (
            attrs["provider"] == EmailIntegration.Provider.ZOHO
            and not attrs.get("zoho_data_center")
        ):
            attrs["zoho_data_center"] = "IN"
        if (
            attrs["provider"] != EmailIntegration.Provider.ZOHO
            and attrs.get("zoho_data_center")
        ):
            raise serializers.ValidationError(
                {"zoho_data_center": "This field is only valid for Zoho Mail."}
            )
        return attrs


class EmailIntegrationConfigureSerializer(serializers.Serializer):
    initial_sync_from_at = serializers.DateTimeField()

    def validate_initial_sync_from_at(self, value):
        if value > timezone.now():
            raise serializers.ValidationError("Initial sync time cannot be in the future.")
        return value


class EmailOAuthCallbackSerializer(serializers.Serializer):
    state = serializers.CharField(max_length=4096)
    code = serializers.CharField(required=False, max_length=4096)
    error = serializers.CharField(required=False, max_length=512)
    error_description = serializers.CharField(required=False, max_length=1024)


class EmailIntegrationSerializer(serializers.ModelSerializer):
    initial_sync_configured = serializers.SerializerMethodField()
    token_expires_in_seconds = serializers.SerializerMethodField()

    class Meta:
        model = EmailIntegration
        fields = (
            "id",
            "provider",
            "mailbox_email",
            "display_name",
            "ocr_template",
            "status",
            "is_active",
            "is_paused",
            "sync_interval_minutes",
            "initial_sync_from_at",
            "initial_sync_configured",
            "last_successful_sync_at",
            "next_sync_at",
            "last_error",
            "consecutive_failures",
            "token_expires_in_seconds",
            "created_at",
            "updated_at",
        )

    @staticmethod
    def get_initial_sync_configured(obj):
        return obj.initial_sync_from_at is not None

    @staticmethod
    def get_token_expires_in_seconds(obj):
        if not obj.access_token_expires_at:
            return None
        return max(int((obj.access_token_expires_at - timezone.now()).total_seconds()), 0)
