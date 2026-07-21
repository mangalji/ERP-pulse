"""
Reports API views.

Views only: authenticate, validate the `months` query param, call
ReportsService, return the standard response envelope — matching
dashboard/views.py's layering.
"""

from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from common.throttles import NetSuiteSyncThrottle
from common.utils.response import success_response
from reports.services import DEFAULT_MONTHS, ReportsService


class SalesTrendView(APIView):
    """
    GET /api/v1/reports/sales-trend/?months=6

    Uses NetSuiteSyncThrottle (not DashboardThrottle) since, like the
    netsuite/ record endpoints, this issues live SuiteQL calls rather
    than reading cached/local data.
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [NetSuiteSyncThrottle]

    def get(self, request):
        months = request.query_params.get('months', DEFAULT_MONTHS)
        trend = ReportsService().get_sales_trend(user=request.user, months=months)
        return success_response(
            message='Sales trend fetched successfully.',
            data=trend,
        )