"""
Middleware that records one RequestLog row per API request.

Only requests under /api/v1/ are logged — Django admin, static files, and
health-check pings to `/` aren't API usage. Logging failures are swallowed
(never let monitoring break the actual request) and logging itself never
recurses, since RequestLog writes don't go through this same middleware
stack in a way that re-triggers it.
"""

import logging
import os
import time
from django.db import connection

logger = logging.getLogger(__name__)

MONITORED_PREFIX = "/api/v1/"
# Endpoints excluded from logging: the monitoring endpoints themselves,
# so viewing the dashboard doesn't inflate its own numbers.
# EXCLUDED_PREFIXES = ("/api/v1/monitoring/",)

EXCLUDED_PREFIXES = (
    "/api/v1/monitoring/health/",
    "/api/v1/monitoring/api-usage/",
    "/api/v1/monitoring/errors/",
)
class RequestMonitoringMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path
        monitored = (
            path.startswith(MONITORED_PREFIX)
            and not path.startswith(EXCLUDED_PREFIXES)
        )
        diagnostics_enabled = (
            os.getenv("LATENCY_DIAGNOSTICS","false").lower()
            in {"1","true","yes"}
        )
        stats = {
            "db_queries": 0,
            "db_time_ms": 0.0,
        }

        def time_query(execute,sql,params,many,context):
            query_start = time.perf_counter()
            try:
                return execute(sql,params,many,context)
            finally:
                stats["db_queries"]+= 1
                stats["db_time_ms"] += (
                    time.perf_counter() - query_start
                ) * 1000

        start = time.perf_counter()

        try:
            if monitored and diagnostics_enabled:
                # Observe SQL execution without logging SQL or parameters.
                with connection.execute_wrapper(time_query):
                    response = self.get_response(request)
            else:
                response = self.get_response(request)
        except Exception:
            total_ms = (time.perf_counter() - start) * 1000

            if monitored and diagnostics_enabled:
                logger.exception(
                    "LATENCY_DIAG method=%s path=%s status=500 "
                    "total_ms=%.2f db_queries=%d db_time_ms=%.2f",
                    request.method,path,total_ms,stats["db_queries"],stats["db_time_ms"]
                )
            raise
        total_ms = (time.perf_counter() - start) * 1000

        if monitored:
            if diagnostics_enabled:
                other_ms = max(0.0,total_ms-stats["db_time_ms"])
                logger.info(
                    "LATENCY_DIAG method=%s path=%s status=%s "
                    "total_ms=%.2f db_queries=%d "
                    "db_time_ms=%.2f other_ms=%.2f",
                    request.method,path,response.status_code,total_ms,stats["db_queries"],stats["db_time_ms"],other_ms
                    )
            self._log(request,response,total_ms)
        # Always hand the response back. Returning only inside `if monitored`
        # made every unmonitored path (/, /admin/, /api/v1/monitoring/health/)
        # return None, which Django turns into an HTTP 500.
        return response

    def _log(self, request, response, duration_ms):
        if os.getenv("REQUEST_LOG_TO_DATABASE", "true").lower() not in {"1","true","yes"}:
            return
        try:
            from monitoring.models import RequestLog

            user = getattr(request, "user", None)
            RequestLog.objects.create(
                method=request.method,
                path=request.path,
                status_code=response.status_code,
                response_time_ms=round(duration_ms, 2),
                is_throttled=response.status_code == 429,
                user=user if user and user.is_authenticated else None,
            )
        except Exception:
            # Monitoring must never break the request it's observing.
            logger.exception("Failed to write RequestLog entry.")
