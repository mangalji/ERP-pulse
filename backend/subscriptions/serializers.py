from rest_framework import serializers
from tenancy.models import Company
from superadmin.models import Plan


class SubscriptionSerializer(serializers.ModelSerializer):
    plan_name = serializers.CharField(source='plan.name', read_only=True,allow_null=True,)
    # plan_code = serializers.CharField(source='plan.code', read_only=True,allow_null=True,)
    company_name = serializers.CharField(source='name', read_only=True)
    subscription_status = serializers.SerializerMethodField()
    start_date = serializers.DateField(
        source='plan_start_date',
        read_only=True,
        allow_null=True,
    )
    end_date = serializers.DateField(
        source='plan_end_date',
        read_only=True,
        allow_null=True,
    )

    class Meta:
        model = Company
        fields = [
            'id',
            'name',
            'company_name',
            'plan',
            'plan_name',
            'plan_code',
            'plan_start_date',
            'plan_end_date',
            'start_date',
            'end_date',
            'subscription_status',
        ]
        read_only_fields = [
            'id',
            'name',
            'company_name',
            'plan_name',
            'plan_code',
            'plan_start_date',
            'plan_end_date',
            'start_date',
            'end_date',
            'subscription_status',
        ]

    def get_subscription_status(self, obj):
        from tenancy.services import company_lifecycle_service

        status = company_lifecycle_service.get_effective_status(
            company=obj
        )

        if status in ['ACTIVE', 'TRIAL']:
            return 'ACTIVE'

        return 'NO_ACTIVE_PLAN'

class PlanSerializer(serializers.ModelSerializer):

    class Meta:
        model = Plan
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'updated_at')
