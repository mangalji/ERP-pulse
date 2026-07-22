"""
Sync API views.

Views only: authenticate, validate input, call SyncManager, return the
standard response envelope — same layering as netsuite/views.py and
reports/views.py. SyncRunListCreateView mirrors
netsuite.views.NetSuiteConnectionListCreateView's GET (list) + POST
(create) convention.
"""

from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from common.throttles import NetSuiteSyncThrottle
from common.utils.response import success_response
from sync.serializers import SyncRunSerializer, TriggerSyncSerializer
from sync.services import SyncManager


class SyncRunListCreateView(APIView):
    """
    GET  /api/v1/sync/runs/ — sync history for the active connection.
    POST /api/v1/sync/runs/ — start a new sync run.
    """

    permission_classes = [IsAuthenticated]

    def get_throttles(self):
        # Only the write path (starting a sync) needs the NetSuite-call
        # throttle — listing history reads local data, no NetSuite call.
        if self.request.method == 'POST':
            return [NetSuiteSyncThrottle()]
        return []

    def get(self, request):
        runs = SyncManager().list_runs(user=request.user)
        return success_response(
            message='Sync history fetched successfully.',
            data=SyncRunSerializer(runs, many=True).data,
        )

    def post(self, request):
        serializer = TriggerSyncSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        run = SyncManager().trigger_sync(
            user=request.user,
            record_types=serializer.validated_data.get('record_types'),
        )
        return success_response(
            message='Sync started.',
            data=SyncRunSerializer(run).data,
        )


class SyncRunDetailView(APIView):
    """GET /api/v1/sync/runs/{id}/ — one run's status and per-stage detail."""

    permission_classes = [IsAuthenticated]

    def get(self, request, run_id):
        run = SyncManager().get_run(user=request.user, run_id=run_id)
        return success_response(
            message='Sync run fetched successfully.',
            data=SyncRunSerializer(run).data,
        )


class RetrySyncRunView(APIView):
    """POST /api/v1/sync/runs/{id}/retry/ — retry only this run's failed stages."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [NetSuiteSyncThrottle]

    def post(self, request, run_id):
        run = SyncManager().retry_failed_stages(user=request.user, run_id=run_id)
        return success_response(
            message='Failed stages retried.',
            data=SyncRunSerializer(run).data,
        )
