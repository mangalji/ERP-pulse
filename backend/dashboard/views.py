"""
Dashboard API views.

Views only: authenticate, call DashboardService, return the standard
response envelope. No NetSuite calls happen here — DashboardService is
the only thing this module talks to, and DashboardService in turn only
talks to the existing NetSuiteDataService, matching the layering already
used by accounts/ and netsuite/.
"""

from rest_framework import permissions
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.views import APIView

from common.utils.pagination import paginated_response
from common.utils.response import success_response
from common.throttles import DashboardThrottle
from dashboard.services import DashboardService, DashboardAggregateService


class DashboardIsAuthenticated(permissions.BasePermission):
    message = 'Authentication credentials were not provided.'

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            raise AuthenticationFailed(self.message)
        return True


def _get_dashboard_service() -> DashboardService:
    return DashboardService()


def _parse_pagination_params(request, default_limit=20):
    """Extract and validate offset/limit from query params."""
    try:
        offset = int(request.query_params.get("offset", 0))
    except (ValueError, TypeError):
        offset = 0
    try:
        limit = int(request.query_params.get("limit", default_limit))
    except (ValueError, TypeError):
        limit = default_limit
    offset = max(0, offset)
    limit = max(1, min(limit, 100))
    return offset, limit


class DashboardSummaryView(APIView):
    """GET /api/v1/dashboard/summary/"""

    permission_classes = [permissions.AllowAny]
    throttle_classes = [DashboardThrottle]

    def get(self, request):
        if not request.user or not request.user.is_authenticated:
            return success_response(
                message='Authentication credentials were not provided.',
                data={},
                status_code=401,
            )

        summary = _get_dashboard_service().get_summary(user=request.user)
        return success_response(
            message='Dashboard summary fetched successfully.',
            data=summary,
        )


class RecentSalesOrdersView(APIView):
    """GET /api/v1/dashboard/recent-sales-orders/"""

    permission_classes = [permissions.AllowAny]
    throttle_classes = [DashboardThrottle]

    def get(self, request):
        if not request.user or not request.user.is_authenticated:
            return success_response(
                message='Authentication credentials were not provided.',
                data={},
                status_code=401,
            )

        offset, limit = _parse_pagination_params(request)
        all_orders = _get_dashboard_service().get_recent_sales_orders(user=request.user)
        count = len(all_orders)
        page = all_orders[offset:offset + limit]
        return paginated_response(
            message='Recent sales orders fetched successfully.',
            results=page,
            count=count,
            request=request,
            offset=offset,
            limit=limit,
        )


class RecentInvoicesView(APIView):
    """GET /api/v1/dashboard/recent-invoices/"""

    permission_classes = [permissions.AllowAny]
    throttle_classes = [DashboardThrottle]

    def get(self, request):
        if not request.user or not request.user.is_authenticated:
            return success_response(
                message='Authentication credentials were not provided.',
                data={},
                status_code=401,
            )

        offset, limit = _parse_pagination_params(request)
        all_invoices = _get_dashboard_service().get_recent_invoices(user=request.user)
        count = len(all_invoices)
        page = all_invoices[offset:offset + limit]
        return paginated_response(
            message='Recent invoices fetched successfully.',
            results=page,
            count=count,
            request=request,
            offset=offset,
            limit=limit,
        )

class RecentCustomersView(APIView):
    """GET /api/v1/dashboard/recent-customers/"""

    permission_classes = [permissions.AllowAny]
    throttle_classes = [DashboardThrottle]

    def get(self, request):
        if not request.user or not request.user.is_authenticated:
            return success_response(
                message='Authentication credentials were not provided.',
                data={},
                status_code=401,
            )

        offset, limit = _parse_pagination_params(request)
        all_customers = _get_dashboard_service().get_recent_customers(user=request.user)
        count = len(all_customers)
        page = all_customers[offset:offset + limit]
        return paginated_response(
            message='Recent customers fetched successfully.',
            results=page,
            count=count,
            request=request,
            offset=offset,
            limit=limit,
        )


class ExecutiveSummaryView(APIView):
    """GET /api/v1/dashboard/executive-summary/"""

    permission_classes = [permissions.AllowAny]
    throttle_classes = [DashboardThrottle]

    def get(self, request):
        if not request.user or not request.user.is_authenticated:
            return success_response(
                message='Authentication credentials were not provided.',
                data={},
                status_code=401,
            )

        data = DashboardAggregateService().get_executive_summary(user=request.user)
        return success_response(
            message='Executive summary fetched successfully.',
            data=data,
        )


class ExecutiveChartsView(APIView):
    """GET /api/v1/dashboard/executive-charts/"""

    permission_classes = [permissions.AllowAny]
    throttle_classes = [DashboardThrottle]

    def get(self, request):
        if not request.user or not request.user.is_authenticated:
            return success_response(
                message='Authentication credentials were not provided.',
                data={},
                status_code=401,
            )

        service = DashboardAggregateService()
        data = {
            'invoice_charts': service.get_invoice_charts(user=request.user),
            'employee_growth': service.get_employee_growth(user=request.user),
            'ai_usage': service.get_ai_usage(user=request.user),
        }
        return success_response(
            message='Executive charts fetched successfully.',
            data=data,
        )


class ActivityFeedView(APIView):
    """GET /api/v1/dashboard/activity-feed/"""

    permission_classes = [permissions.AllowAny]
    throttle_classes = [DashboardThrottle]

    def get(self, request):
        if not request.user or not request.user.is_authenticated:
            return success_response(
                message='Authentication credentials were not provided.',
                data={},
                status_code=401,
            )

        try:
            limit = int(request.query_params.get('limit', 10))
        except (TypeError, ValueError):
            limit = 10
        limit = max(1, min(limit, 50))

        data = DashboardAggregateService().get_activity_feed(user=request.user, limit=limit)
        return success_response(
            message='Activity feed fetched successfully.',
            data=data,
        )
