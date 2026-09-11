"""
Subscription & License API views.

Views are intentionally thin — they validate input via serializers,
delegate business logic to services, and format the standard success envelope.
"""

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from audit.models import AuditAction, AuditModule
from audit.services import audit_service
from common.utils.pagination import paginated_response
from common.utils.response import success_response
from tenancy.models import Company
from subscriptions.permissions import IsSuperAdminOrCompanyAdmin
from subscriptions.serializers import PlanSerializer, SubscriptionSerializer
from subscriptions.services import subscription_service
from superadmin.models import Plan

class SubscriptionViewSet(viewsets.ViewSet):
    """Subscription management for super admins and company admins."""

    def get_permissions(self):
        if self.action in ['my_subscription']:
            return [IsAuthenticated()]
        return [IsSuperAdminOrCompanyAdmin()]

    @action(detail=False, methods=['get'], url_path='my')
    def my_subscription(self, request):
        """GET /api/v1/subscriptions/my/ — client company current subscription."""
        company = getattr(request.user, 'company', None)
        if not company:
            return Response({'detail': 'No company associated with user.'}, status=status.HTTP_404_NOT_FOUND)

        subscription = subscription_service.get_active_subscription(company_id=company.id)
        if not subscription:
            return Response({'detail': 'No active subscription found.'}, status=status.HTTP_404_NOT_FOUND)

        return success_response(
            message='Current subscription fetched successfully.',
            data=SubscriptionSerializer(subscription).data,
        )

    @action(detail=False, methods=['get'], url_path='my-transactions')
    def my_transactions(self, request):
        """GET /api/v1/subscriptions/my-transactions/ — client company transactions."""
        company = getattr(request.user, 'company', None)
        if not company:
            return Response({'detail': 'No company associated with user.'}, status=status.HTTP_404_NOT_FOUND)

        from superadmin.models import Transaction
        from superadmin.serializers import TransactionSerializer
        transactions = Transaction.objects.filter(company=company).select_related('plan').order_by('-created_at')
        return success_response(
            message='Transactions fetched successfully.',
            data=TransactionSerializer(transactions, many=True).data,
        )

    @action(detail=False, methods=['post'])
    def assign(self, request):
        """POST /api/v1/subscriptions/assign/ — assign plan to company."""
        company_id = request.data.get('company_id')
        plan_id = request.data.get('plan_id')
        status_value = request.data.get('status')
        discount_type = request.data.get('discount_type')
        discount_value = request.data.get('discount_value')
        billing_cycle = request.data.get('billing_cycle')
        if not company_id or not plan_id:
            return Response({'detail': 'company_id and plan_id are required.'}, status=status.HTTP_400_BAD_REQUEST)

        company_plan = subscription_service.assign_plan(
            company_id=company_id,
            plan_id=plan_id,
            status=status_value,
            discount_type=discount_type,
            discount_value=discount_value,
            billing_cycle=billing_cycle,
            request=request,
        )
        return success_response(
            message='Plan assigned successfully.',
            data=SubscriptionSerializer(company_plan).data,
        )

    @action(detail=False, methods=['post'])
    def upgrade(self, request):
        """POST /api/v1/subscriptions/upgrade/ — upgrade company plan."""
        company_id = request.data.get('company_id')
        plan_id = request.data.get('plan_id')
        discount_type = request.data.get('discount_type')
        discount_value = request.data.get('discount_value')
        billing_cycle = request.data.get('billing_cycle')
        if not company_id or not plan_id:
            return Response({'detail': 'company_id and plan_id are required.'}, status=status.HTTP_400_BAD_REQUEST)

        company_plan = subscription_service.upgrade_plan(
            company_id=company_id,
            plan_id=plan_id,
            discount_type=discount_type,
            discount_value=discount_value,
            billing_cycle=billing_cycle,
            request=request,
        )
        return success_response(
            message='Plan upgraded successfully.',
            data=SubscriptionSerializer(company_plan).data,
        )

    @action(detail=False, methods=['post'])
    def downgrade(self, request):
        """POST /api/v1/subscriptions/downgrade/ — downgrade company plan."""
        company_id = request.data.get('company_id')
        plan_id = request.data.get('plan_id')
        discount_type = request.data.get('discount_type')
        discount_value = request.data.get('discount_value')
        billing_cycle = request.data.get('billing_cycle')
        if not company_id or not plan_id:
            return Response({'detail': 'company_id and plan_id are required.'}, status=status.HTTP_400_BAD_REQUEST)

        company_plan = subscription_service.downgrade_plan(
            company_id=company_id,
            plan_id=plan_id,
            discount_type=discount_type,
            discount_value=discount_value,
            billing_cycle=billing_cycle,
            request=request,
        )
        return success_response(
            message='Plan downgraded successfully.',
            data=SubscriptionSerializer(company_plan).data,
        )

    @action(detail=False, methods=['post'])
    def renew(self, request):
        """POST /api/v1/subscriptions/renew/ — renew company plan."""
        company_id = request.data.get('company_id')
        plan_id = request.data.get('plan_id')
        discount_type = request.data.get('discount_type')
        discount_value = request.data.get('discount_value')
        billing_cycle = request.data.get('billing_cycle')
        if not company_id:
            return Response({'detail': 'company_id is required.'}, status=status.HTTP_400_BAD_REQUEST)

        company_plan = subscription_service.renew_plan(
            company_id=company_id,
            plan_id=plan_id,
            discount_type=discount_type,
            discount_value=discount_value,
            billing_cycle=billing_cycle,
            request=request,
        )
        return success_response(
            message='Plan renewed successfully.',
            data=SubscriptionSerializer(company_plan).data,
        )

    @action(detail=False, methods=['post'])
    def cancel(self, request):
        """POST /api/v1/subscriptions/cancel/ — cancel company plan."""
        company_id = request.data.get('company_id')
        if not company_id:
            return Response({'detail': 'company_id is required.'}, status=status.HTTP_400_BAD_REQUEST)

        company_plan = subscription_service.cancel_plan(
            company_id=company_id,
            request=request,
        )
        return success_response(
            message='Plan cancelled successfully.',
            data=SubscriptionSerializer(company_plan).data,
        )

    @action(detail=False, methods=['get'], url_path='plans')
    def list_plans(self, request):
        """GET /api/v1/subscriptions/plans/ — list available plans."""
        plans = Plan.objects.filter(is_deleted=False)
        return success_response(
            message='Plans fetched successfully.',
            data=PlanSerializer(plans, many=True).data,
        )
