"""
Dashboard API views.

Views only: authenticate, call DashboardService, return the standard
response envelope. No NetSuite calls happen here — DashboardService is
the only thing this module talks to, and DashboardService in turn only
talks to the existing NetSuiteDataService, matching the layering already
used by accounts/ and netsuite/.
"""

from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from common.utils.pagination import paginated_response
from common.utils.response import success_response
from common.throttles import DashboardThrottle
from dashboard.services import DashboardService

dashboard_service = DashboardService()


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

    permission_classes = [IsAuthenticated]
    throttle_classes = [DashboardThrottle]

    def get(self, request):
        summary = dashboard_service.get_summary(user=request.user)
        return success_response(
            message='Dashboard summary fetched successfully.',
            data=summary,
        )


class RecentSalesOrdersView(APIView):
    """GET /api/v1/dashboard/recent-sales-orders/"""

    permission_classes = [IsAuthenticated]
    throttle_classes = [DashboardThrottle]

    def get(self, request):
        offset, limit = _parse_pagination_params(request)
        all_orders = dashboard_service.get_recent_sales_orders(user=request.user)
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

    permission_classes = [IsAuthenticated]
    throttle_classes = [DashboardThrottle]

    def get(self, request):
        offset, limit = _parse_pagination_params(request)
        all_invoices = dashboard_service.get_recent_invoices(user=request.user)
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

    permission_classes = [IsAuthenticated]
    throttle_classes = [DashboardThrottle]

    def get(self, request):
        offset, limit = _parse_pagination_params(request)
        all_customers = dashboard_service.get_recent_customers(user=request.user)
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
