from rest_framework import serializers
from tenancy.models import Company, CompanyModule, Module
from superadmin.models import Plan, CompanyPlan, CompanyPlanStatus


class SubscriptionSerializer(serializers.ModelSerializer):
    plan_name = serializers.CharField(source='plan.name', read_only=True)
    plan_code = serializers.CharField(source='plan.code', read_only=True)
    company_name = serializers.CharField(source='company.name', read_only=True)

    class Meta:
        model = CompanyPlan
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'updated_at')


class UsageSerializer(serializers.ModelSerializer):
    module_name = serializers.CharField(source='module.name', read_only=True)
    module_code = serializers.CharField(source='module.code', read_only=True)

    class Meta:
        model = CompanyModule
        fields = (
            'id',
            'module',
            'module_name',
            'module_code',
            'enabled',
            'usage_limit',
            'usage_count',
            'last_usage_reset',
            'activated_at',
        )
        read_only_fields = ('id', 'created_at', 'updated_at')


class ModuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Module
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'updated_at')


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
