from rest_framework import serializers
from .models import Invitation, InvitationStatus
from tenancy.models import Company
from rbac.models import Role
from django.contrib.auth import get_user_model

User = get_user_model()


class InvitationSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source='company.name', read_only=True)
    role_name = serializers.CharField(source='role.name', read_only=True)
    created_by_email = serializers.CharField(source='created_by.email', read_only=True)

    class Meta:
        model = Invitation
        fields = (
            'id',
            'token',
            'email',
            'company',
            'company_name',
            'role',
            'role_name',
            'status',
            'expires_at',
            'accepted_at',
            'created_by',
            'created_by_email',
            'created_at',
            'updated_at',
        )
        read_only_fields = (
            'id',
            'token',
            'created_at',
            'updated_at',
        )


class CreateInvitationSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=100)
    company_id = serializers.UUIDField()
    role_id = serializers.UUIDField(required=False, allow_null=True)
    expires_in_days = serializers.IntegerField(required=False, default=7, min_value=1, max_value=30)

    def validate_company_id(self, value):
        if not Company.objects.filter(pk=value).exists():
            raise serializers.ValidationError('Company not found.')
        return value

    def validate_role_id(self, value):
        if value is not None and not Role.objects.filter(pk=value).exists():
            raise serializers.ValidationError('Role not found.')
        return value


class RequestInvitationOTPSerializer(serializers.Serializer):
    token = serializers.UUIDField()
    password = serializers.CharField(write_only=True, min_length=8, max_length=128)
    confirm_password = serializers.CharField(write_only=True, min_length=8, max_length=128)
    # first_name = serializers.CharField(max_length=150)
    # last_name = serializers.CharField(max_length=150)

    def validate(self, attrs):
        if attrs['password'] != attrs.pop('confirm_password'):
            raise serializers.ValidationError({'confirm_password': 'Passwords do not match.'})
        return attrs

class AcceptInvitationSerializer(serializers.Serializer):
    token = serializers.UUIDField()
    password = serializers.CharField(
        write_only=True,
        max_length=128,
        min_length=8,
    )
    otp = serializers.CharField(
        write_only=True,
        min_length=6,
        max_length=6,
    )

class InvitationValidateSerializer(serializers.Serializer):
    token = serializers.UUIDField()
