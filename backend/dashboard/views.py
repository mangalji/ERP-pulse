"""Dashboard API views.

Views handle authentication and delegate dashboard operations
to the dashboard aggregate service.
"""

from rest_framework import permissions
from rest_framework.views import APIView
from netsuite.exceptions import NetSuiteConnectionNotFoundException
from common.pagination import paginated_response
from common.common_utils import success_response
from common.throttles import DashboardThrottle
from dashboard.services import DashboardAggregateService


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
