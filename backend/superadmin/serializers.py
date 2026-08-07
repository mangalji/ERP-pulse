from rest_framework import serializers
from .models import Plan, CompanyPlan, SupportSession
from tenancy.models import Company, CompanyModule, Module
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


class PlanDetailSerializer(serializers.ModelSerializer):
    """Extended plan serializer for detail page."""
    enabled_modules = serializers.SerializerMethodField()
    included_modules_count = serializers.SerializerMethodField()

    class Meta:
        model = Plan
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'updated_at')

    def get_enabled_modules(self, obj):
        return [
            {
                'id': m.id,
                'name': m.name,
                'code': m.code,
                'display_name': m.display_name,
            }
            for m in obj.enabled_models.all()
        ]

    def get_included_modules_count(self, obj):
        return obj.enabled_models.count()


class CompanyPlanSummarySerializer(serializers.ModelSerializer):
    """Lightweight plan summary for company detail page."""
    plan_name = serializers.CharField(source='plan.name', read_only=True)

    class Meta:
        model = CompanyPlan
        fields = ['id', 'plan_name', 'status', 'start_date', 'end_date', 'is_auto_renew']


class CompanyDetailSerializer(serializers.ModelSerializer):
    """Extended company serializer for the detail page.
    Includes subscription plan, assigned modules, employee stats, and NetSuite connection status.
    """
    user_count = serializers.SerializerMethodField()
    module_count = serializers.SerializerMethodField()
    active_user_count = serializers.SerializerMethodField()
    current_plan = serializers.SerializerMethodField()
    assigned_modules = serializers.SerializerMethodField()
    netsuite_connected = serializers.SerializerMethodField()
    netsuite_account_id = serializers.SerializerMethodField()
    netsuite_environment = serializers.SerializerMethodField()
    netsuite_last_sync = serializers.SerializerMethodField()

    class Meta:
        model = Company
        fields = [
            'id', 'name', 'code', 'status', 'contact_email', 'contact_phone',
            'country', 'created_at', 'updated_at',
            'user_count', 'active_user_count', 'module_count',
            'current_plan', 'assigned_modules',
            'netsuite_connected', 'netsuite_account_id', 'netsuite_environment', 'netsuite_last_sync',
        ]
        read_only_fields = fields

    def get_user_count(self, obj):
        return obj.users.count()

    def get_active_user_count(self, obj):
        return obj.users.filter(is_active=True).count()

    def get_module_count(self, obj):
        return obj.company_modules.count()

    def get_current_plan(self, obj):
        plan = obj.company_plans.filter(
            status__in=['ACTIVE', 'TRIAL']
        ).select_related('plan').first()
        if plan:
            return CompanyPlanSummarySerializer(plan).data
        return None

    def get_assigned_modules(self, obj):
        modules = obj.company_modules.select_related('module').filter(enabled=True)
        return [
            {
                'id': cm.module.id,
                'name': cm.module.name,
                'code': cm.module.code,
                'display_name': cm.module.display_name,
                'enabled': cm.enabled,
            }
            for cm in modules
        ]

    def get_netsuite_connected(self, obj):
        return obj.netsuite_connections.filter(is_active=True).exists()

    def get_netsuite_account_id(self, obj):
        conn = obj.netsuite_connections.filter(is_active=True).first()
        return conn.netsuite_account_id if conn else None

    def get_netsuite_environment(self, obj):
        conn = obj.netsuite_connections.filter(is_active=True).first()
        return conn.get_environment_display() if conn and conn.environment else None

    def get_netsuite_last_sync(self, obj):
        conn = obj.netsuite_connections.filter(is_active=True).first()
        return conn.last_synced_at if conn else None


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