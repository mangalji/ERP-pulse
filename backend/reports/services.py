"""
Business logic for the Reports module.

Phase 3 (Analytics & AI Architecture): Reports consumes AnalyticsService
rather than running its own NetSuite aggregation queries. Previously
this file had its own duplicate SuiteQL month-trend query — that logic
now lives in analytics/services.py's AnalyticsService.get_sales_trend_by_month(),
alongside every other KPI calculation in the project, so Dashboard,
Reports, and AI all share one source of truth instead of drifting apart.
"""

from accounts.models import User
from analytics.services import AnalyticsService

DEFAULT_MONTHS = 6
MAX_MONTHS = 24


class ReportsService:
    def __init__(self, analytics_service: AnalyticsService | None = None):
        self.analytics_service = analytics_service or AnalyticsService()

    def get_sales_trend(self, *, user: User, months: int = DEFAULT_MONTHS) -> dict:
        return self.analytics_service.get_sales_trend_by_month(user=user, months=months)
