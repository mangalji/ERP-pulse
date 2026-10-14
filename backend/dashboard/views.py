"""Dashboard API views.

Views handle authentication and delegate dashboard operations
to the dashboard aggregate service.
"""

from rest_framework import permissions
from rest_framework.views import APIView
from common.common_utils import success_response
from common.throttles import DashboardThrottle
from dashboard.services import DashboardAggregateService

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
