"""
Monitoring API views.

- HealthCheckView is intentionally AllowAny and unauthenticated: it's
  meant to be hit by Render's own health checks or an external uptime
  pinger (e.g. UptimeRobot) that has no JWT.
- ReadinessView is a lightweight, DB-only check for orchestrated environments.
- ErrorLogListView and ApiUsageView expose internal operational data
  (stack traces, request volume) so they're restricted to staff users
  (IsAdminUser -> request.user.is_staff), not just any authenticated user.
"""

from datetime import timedelta

from django.db import connection as db_connection
from django.db.models import Avg, Count, Q
from django.conf import settings
from django.utils import timezone
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.views import APIView

from common.utils.response import success_response
from monitoring.models import ErrorLog, RequestLog
from monitoring.serializers import ErrorLogSerializer


class HealthCheckView(APIView):
    """
    GET /api/v1/monitoring/health/

    Checks the dependencies ERP Pulse actually needs to function:
    - database: a real query, since this is the one dependency that must
      be live for almost anything to work.
    - email: configuration presence only (not a live SMTP handshake —
      that would make every health check slow and could itself trip
      Gmail's rate limits).
    - netsuite_encryption: FIELD_ENCRYPTION_KEY must be set or no
      NetSuite connection can be created or used.

    Overall status is "healthy" only if every check passes, "degraded"
    if a non-critical check (email, encryption config) fails, and "down"
    if the database check fails.
    """

    permission_classes = [AllowAny]

    def get(self, request):
        checks = {
            "database": self._check_database(),
            "email": self._check_email(),
            "netsuite_encryption": self._check_encryption(),
        }

        if not checks["database"]["ok"]:
            overall = "down"
        elif all(c["ok"] for c in checks.values()):
            overall = "healthy"
        else:
            overall = "degraded"

        return success_response(
            message="Health check complete.",
            data={
                "status": overall,
                "checked_at": timezone.now(),
                "checks": checks,
            },
        )

    def _check_database(self):
        try:
            with db_connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            return {"ok": True, "detail": "Database reachable."}
        except Exception as exc:
            return {"ok": False, "detail": str(exc)}

    def _check_email(self):
        if settings.EMAIL_BACKEND.endswith("smtp.EmailBackend") and settings.EMAIL_HOST:
            return {"ok": True, "detail": f"SMTP configured ({settings.EMAIL_HOST})."}
        return {"ok": False, "detail": "SMTP not configured — falling back to console backend."}

    def _check_encryption(self):
        if settings.FIELD_ENCRYPTION_KEY:
            return {"ok": True, "detail": "Field encryption key set."}
        return {"ok": False, "detail": "FIELD_ENCRYPTION_KEY is not set."}


class ReadinessView(APIView):
    """
    GET /api/v1/monitoring/readiness/

    Lightweight, fast — checks only if the database is reachable.
    Unlike the HealthCheckView, this does NOT check encryption key or
    email configuration, so a non-critical config gap never causes
    a readiness failure and unnecessary pod restart in orchestrated
    environments.
    """

    permission_classes = [AllowAny]

    def get(self, request):
        from django.db import connection as db_connection
        from django.db.utils import OperationalError
        from rest_framework.response import Response

        try:
            with db_connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            return success_response(
                message="Service is ready.",
                data={"status": "ready", "database": "connected"},
            )
        except OperationalError:
            return Response(
                status=503,
                data={
                    "success": False,
                    "message": "Service Unavailable",
                    "data": {"status": "not ready", "database": "disconnected"},
                },
            )


class ErrorLogListView(APIView):
    """
    GET /api/v1/monitoring/errors/?limit=50

    Most recent unhandled exceptions, newest first. Staff only.
    """

    permission_classes = [IsAdminUser]

    def get(self, request):
        try:
            limit = int(request.query_params.get("limit", 50))
        except ValueError:
            limit = 50
        limit = max(1,min(limit,200))

        errors = ErrorLog.objects.all()[:limit]
        return success_response(
            message="Recent errors fetched successfully.",
            data=ErrorLogSerializer(errors, many=True).data,
        )


class ApiUsageView(APIView):
    """
    GET /api/v1/monitoring/api-usage/?hours=24

    Aggregated request volume, error rate, throttling, and latency over
    the given window (default last 24 hours). Staff only.
    """

    permission_classes = [IsAdminUser]

    def get(self, request):
        try:
            hours = int(request.query_params.get("hours", 24))
        except ValueError:
            hours = 24
        hours = max(1,min(hours,24 * 30))

        since = timezone.now() - timedelta(hours=hours)
        queryset = RequestLog.objects.filter(created_at__gte=since)

        total_requests = queryset.count()
        error_count = queryset.filter(status_code__gte=400).count()
        throttled_count = queryset.filter(is_throttled=True).count()
        avg_response_time = queryset.aggregate(avg=Avg("response_time_ms"))["avg"] or 0

        top_endpoints = list(
            queryset.values("path", "method")
            .annotate(
                request_count=Count("id"),
                avg_response_time_ms=Avg("response_time_ms"),
                error_count=Count("id", filter=Q(status_code__gte=400)),
            )
            .order_by("-request_count")[:10]
        )

        return success_response(
            message="API usage stats fetched successfully.",
            data={
                "window_hours": hours,
                "total_requests": total_requests,
                "error_count": error_count,
                "error_rate": round(error_count / total_requests, 4) if total_requests else 0,
                "throttled_count": throttled_count,
                "avg_response_time_ms": round(avg_response_time, 2),
                "top_endpoints": top_endpoints,
            },
        )
