from django.contrib.auth.password_validation import validate_password
from django.core.validators import RegexValidator
from rest_framework import serializers

from .models import Invitation, InvitationStatus
from accounts.models import User


# The country and dialling code are administrator-controlled and already
# stored on the invited User. Invitees enter only the national mobile number.
mobile_number_validator = RegexValidator(
    regex=r"^[0-9]{7,15}$",
    message="Enter your mobile number using digits only, without a country code.",
)


class InvitationSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(
        source="company.name",
        read_only=True,
    )
    role_name = serializers.CharField(
        source="role.name",
        read_only=True,
    )
    created_by_email = serializers.CharField(
        source="created_by.email",
        read_only=True,
    )

    class Meta:
        model = Invitation
        fields = (
            "id",
            "token",
            "email",
            "company",
            "company_name",
            "role",
            "role_name",
            "status",
            "expires_at",
            "accepted_at",
            "created_by",
            "created_by_email",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "token",
            "created_at",
            "updated_at",
        )


class RequestInvitationOTPSerializer(serializers.Serializer):
    """
    First invitation-setup step.

    The administrator already created the user's:
    - first name
    - last name
    - country
    - gender

    The invitee supplies their password and confirms the mobile number that
    was entered by the administrator. The service matches that number before
    sending an activation OTP.
    """

    token = serializers.UUIDField()

    password = serializers.CharField(
        write_only=True,
        max_length=128,
        validators=[validate_password],
    )

    confirm_password = serializers.CharField(
        write_only=True,
        max_length=128,
    )

    mobile_number = serializers.CharField(
        write_only=True,
        max_length=15,
        validators=[mobile_number_validator],
    )

    def validate(self, attrs):
        confirm_password = attrs.pop("confirm_password")

        if attrs["password"] != confirm_password:
            raise serializers.ValidationError(
                {"confirm_password": "Passwords do not match."}
            )

        return attrs

class AcceptInvitationSerializer(serializers.Serializer):
    """
    Final invitation acceptance.

    The invitee is NOT allowed to modify administrator-controlled identity
    fields. First name, last name, country, and gender are intentionally
    absent.

    The invitee must confirm the administrator-recorded mobile number. It is
    not editable during invitation acceptance.
    """
    token = serializers.UUIDField()

    password = serializers.CharField(
        write_only=True,
        max_length=128,
        validators=[validate_password],
    )

    otp = serializers.CharField(
        write_only=True,
        min_length=6,
        max_length=6,
        validators=[
            RegexValidator(
                regex=r"^\d{6}$",
                message="OTP must be exactly 6 digits.",
            )
        ],
    )

    mobile_number = serializers.CharField(
        write_only=True,
        max_length=15,
        validators=[mobile_number_validator],
    )


class InvitationValidateSerializer(serializers.Serializer):
    token = serializers.UUIDField()


class EmailDeliverabilitySerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=40)
