from rest_framework import serializers
from django.contrib.auth import get_user_model
import re
from .models import DemoRequest

User = get_user_model()


class DemoRequestSerializer(serializers.ModelSerializer):
    """Serializer for creating and reading demo requests.

    All input validation is performed here (DRF validation) rather than
    in the view. ``assigned_to`` is restricted to AGSuite employees or
    Super Admins (users not tied to a client company).
    """

    assigned_to_name = serializers.CharField(
        source="assigned_to.get_full_name",
        read_only=True,
    )
    # phone = serializers.CharField(validators=[phone_validator])

    class Meta:
        model = DemoRequest
        fields = (
            "id",
            "demo_request_number",
            "company_name",
            "contact_person",
            "business_email",
            "phone",
            "industry",
            "company_size",
            "city",
            "country",
            "message",
            "status",
            "assigned_to",
            "assigned_to_name",
            "notes",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "demo_request_number",
            "status",
            "assigned_to_name",
            "created_at",
            "updated_at",
        )

    def validate_assigned_to(self, value):
        """Only AGSuite employees / Super Admins may be assigned."""
        if value is None:
            return value
        # AGSuite employees are users not attached to a client company.
        if value.company is not None and not getattr(value, "is_superuser", False):
            raise serializers.ValidationError(
                "assigned_to must be an AGSuite employee or Super Admin."
            )
        return value

    def validate_business_email(self, value):
        """Normalize the business email to lowercase."""
        return (value or "").strip().lower()

    def validate(self, attrs):
        """Prevent duplicate active demo requests for the same email."""
        business_email = attrs.get("business_email")
        if business_email:
            active_exists = DemoRequest.objects.filter(
                business_email__iexact=business_email,
            ).exclude(status__in=DemoRequest.CLOSED_STATUSES).exists()
            if active_exists:
                raise serializers.ValidationError(
                    {
                        "business_email": (
                            "An active demo request already exists for this email."
                        )
                    }
                )
        return attrs

    def validate_phone(self, value):
        """Validate phone number format."""
        value= value.strip()
        pattern = r'^\+?[1-9]\d{7,14}$'
        if not re.match(pattern,value):
            raise serializers.ValidationError(
                "Enter a valid phone number."
            )
        return value