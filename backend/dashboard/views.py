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

from common.utils.response import success_response
from common.throttles import DashboardThrottle
from dashboard.services import DashboardService

dashboard_service = DashboardService()


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
        sales_orders = dashboard_service.get_recent_sales_orders(user=request.user)
        return success_response(
            message='Recent sales orders fetched successfully.',
            data={'items': sales_orders},
        )


class RecentInvoicesView(APIView):
    """GET /api/v1/dashboard/recent-invoices/"""

    permission_classes = [IsAuthenticated]
    throttle_classes = [DashboardThrottle]

    def get(self, request):
        invoices = dashboard_service.get_recent_invoices(user=request.user)
        return success_response(
            message='Recent invoices fetched successfully.',
            data={'items': invoices},
        )


class RecentCustomersView(APIView):
    """GET /api/v1/dashboard/recent-customers/"""

    permission_classes = [IsAuthenticated]
    throttle_classes = [DashboardThrottle]

    def get(self, request):
        customers = dashboard_service.get_recent_customers(user=request.user)
        return success_response(
            message='Recent customers fetched successfully.',
            data={'items': customers},
        )
