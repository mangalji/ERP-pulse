from rest_framework import serializers
from .models import Plan, CompanyPlan, SupportSession
from tenancy.models import Company, Module
from django.contrib.auth import get_user_model

User = get_user_model()


class PlanSerializer(serializers.ModelSerializer):
    enabled_models = serializers.SlugRelatedField(
        many=True,
        read_only=True,
        slug_field='code',
    )

    class Meta:
        model = Plan
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'updated_at')


class CompanyPlanSerializer(serializers.ModelSerializer):
    plan_name = serializers.CharField(source='plan.name', read_only=True)
    company_name = serializers.CharField(source='company.name', read_only=True)

    class Meta:
        model = CompanyPlan
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'updated_at')


class SupportSessionSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source='company.name', read_only=True)
    support_user_name = serializers.CharField(source='support_user.get_full_name', read_only=True)
    support_user_email = serializers.EmailField(source='support_user.email',read_only=True)

    class Meta:
        model = SupportSession
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'updated_at')


class CompanySerializer(serializers.ModelSerializer):
    user_count = serializers.IntegerField(
        read_only=True,
    )

    module_count = serializers.IntegerField(
        read_only=True,
    )

    admin_name = serializers.CharField(write_only=True, required=False, allow_blank=True)
    admin_email = serializers.EmailField(write_only=True, required=False, allow_null=True)
    admin_first_name = serializers.CharField(write_only=True, required=False, allow_blank=True)
    admin_last_name = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = Company

        fields = "__all__"

        read_only_fields = (
            "id",
            "created_at",
            "updated_at",
        )

    def create(self, validated_data):
        admin_email = validated_data.pop('admin_email', None)
        admin_first_name = validated_data.pop('admin_first_name', None)
        admin_last_name = validated_data.pop('admin_last_name', None)

        company = super().create(validated_data)

        if admin_email:
            from invitations.services import invitation_service
            from rbac.models import Role
            admin_role = Role.objects.filter(name__iexact='Company Admin', company=None).first()
            invitation_service.create_invitation(
                email=admin_email,
                company_id=company.id,
                role_id=admin_role.id if admin_role else None,
                created_by=None,
            )

        return company


class ModuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Module
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'updated_at')


class CompanyModuleSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source='company.name', read_only=True)
    module_name = serializers.CharField(source='module.name', read_only=True)
    module_code = serializers.CharField(source='module.code', read_only=True)
    company_code = serializers.CharField(
    source="company.code",
    read_only=True,
)

    class Meta:
        from tenancy.models import CompanyModule
        model = CompanyModule
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'updated_at')


class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(
        source="get_full_name",
        read_only=True,
    )

    company_name = serializers.CharField(
        source="company.name",
        read_only=True,
    )

    class Meta:
        model = User

        fields = (
            "id",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "employee_id",
            "designation",
            "department",
            "is_active",
            "is_staff",
            "is_email_verified",
            "last_activity",
            "company",
            "company_name",
        )

        read_only_fields = (
            "id",
            "created_at",
            "updated_at",
        )