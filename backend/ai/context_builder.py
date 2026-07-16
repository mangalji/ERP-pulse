"""
Builds the business context passed to the AI provider.

Per AI_CONTEXT.md ("Facts come from analytics. Explanations come from
AI."), this module never fabricates business data and never fetches raw
NetSuite data itself — it only orchestrates existing services
(DashboardService, BusinessInsightsService) and assembles their results.
All actual NetSuite calls and business-metric logic live in those
services (dashboard/services.py); this module owns none of it.

`netsuite_connected` reflects a real, current check against the user's
actual NetSuiteConnection (reusing netsuite's own repository rather than
querying the model directly here, per DRY). `business_context` is
populated only when connected, combining:

- Dashboard context (summary, recent_customers, recent_sales_orders,
  recent_invoices) — pre-existing keys, unchanged.
- Business Insights (sales_summary, top_customers, overdue_invoices,
  inactive_vendors, low_inventory) — reused from BusinessInsightsService,
  not duplicated here.

Each insight is fetched independently and can fail without failing the
whole request: a failure is logged and that key is set to None (never
fabricated) while every other insight still gets built. An AI request
never crashes just because one specific query is slow or errors — the
assistant still answers using whatever context did come back.
"""

import logging

from accounts.models import User
from dashboard.services import BusinessInsightsService, DashboardService
from netsuite.repositories import NetSuiteConnectionRepository

logger = logging.getLogger(__name__)


def _safe_call(label: str, func):
    """
    Run one context-building call in isolation. On failure, log and
    return None instead of letting the exception propagate — this is
    what makes graceful degradation possible without repeating the same
    try/except block nine times in build_context(). Catches Exception
    broadly and deliberately: any failure mode from an external call
    (network error, unexpected NetSuite response shape, etc.) should
    degrade this one section, not crash the whole AI request — the same
    reasoning netsuite/client.py and ai/providers.py already apply around
    their own external calls.
    """
    try:
        return func()
    except Exception:
        logger.exception('Failed to build AI context section "%s"; omitting it.', label)
        return None


def build_context(user: User) -> dict:
    connection_repository = NetSuiteConnectionRepository()
    connection = connection_repository.get_by_user(user)
    netsuite_connected = bool(connection and connection.is_active)

    business_context = None
    if netsuite_connected:
        dashboard_service = DashboardService()
        business_insights_service = BusinessInsightsService()

        business_context = {
            # Dashboard context — pre-existing keys, unchanged.
            'summary': _safe_call(
                'summary', lambda: dashboard_service.get_summary(user=user)
            ),
            'recent_customers': _safe_call(
                'recent_customers', lambda: dashboard_service.get_recent_customers(user=user)
            ),
            'recent_invoices': _safe_call(
                'recent_invoices', lambda: dashboard_service.get_recent_invoices(user=user)
            ),
            'recent_sales_orders': _safe_call(
                'recent_sales_orders',
                lambda: dashboard_service.get_recent_sales_orders(user=user),
            ),
            # Business Insights — new, additive keys.
            'sales_summary': _safe_call(
                'sales_summary', lambda: business_insights_service.get_sales_summary(user=user)
            ),
            'top_customers': _safe_call(
                'top_customers', lambda: business_insights_service.get_top_customers(user=user)
            ),
            'overdue_invoices': _safe_call(
                'overdue_invoices',
                lambda: business_insights_service.get_overdue_invoices(user=user),
            ),
            'inactive_vendors': _safe_call(
                'inactive_vendors',
                lambda: business_insights_service.get_inactive_vendors(user=user),
            ),
            'low_inventory': _safe_call(
                'low_inventory', lambda: business_insights_service.get_low_inventory(user=user)
            ),
        }

    return {
        'netsuite_connected': netsuite_connected,
        'business_context': business_context,
    }