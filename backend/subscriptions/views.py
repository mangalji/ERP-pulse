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
from common.pagination import paginated_response
from common.common_utils import success_response
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
            return success_response(
                message='No active plan found.',
                data=SubscriptionSerializer(company).data,
            )

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

    @action(detail=False, methods=['get'], url_path='plans')
    def list_plans(self, request):
        """GET /api/v1/subscriptions/plans/ — list available plans."""
        plans = Plan.objects.filter(is_deleted=False,status='ACTIVE')
        return success_response(
            message='Plans fetched successfully.',
            data=PlanSerializer(plans, many=True).data,
        )
