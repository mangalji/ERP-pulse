"""
Middleware that records one RequestLog row per API request.

Only requests under /api/v1/ are logged — Django admin, static files, and
health-check pings to `/` aren't API usage. Logging failures are swallowed
(never let monitoring break the actual request) and logging itself never
recurses, since RequestLog writes don't go through this same middleware
stack in a way that re-triggers it.
"""

import logging
import time

logger = logging.getLogger(__name__)

MONITORED_PREFIX = "/api/v1/"
# Endpoints excluded from logging: the monitoring endpoints themselves,
# so viewing the dashboard doesn't inflate its own numbers.
EXCLUDED_PREFIXES = ("/api/v1/monitoring/",)


class RequestMonitoringMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start = time.monotonic()
        response = self.get_response(request)

        path = request.path
        if path.startswith(MONITORED_PREFIX) and not path.startswith(EXCLUDED_PREFIXES):
            duration_ms = (time.monotonic() - start) * 1000
            self._log(request, response, duration_ms)

        return response

    def _log(self, request, response, duration_ms):
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