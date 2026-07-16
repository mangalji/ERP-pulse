"""
Builds the business context passed to the AI provider.

Per AI_CONTEXT.md ("Facts come from analytics. Explanations come from
AI.") and the explicit rule for this task, this module never fabricates
business data. `netsuite_connected` reflects a real, current check against
the user's actual NetSuiteConnection (reusing netsuite's own repository
rather than querying the model directly here, per DRY) — it is not
hardcoded, since hardcoding it would become an outright lie the moment a
real connection exists. `business_context` stays None until a future task
adds real NetSuite data fetching (an analytics layer, per AI_CONTEXT.md's
"AI receives structured metrics only" rule) — that data-fetching step is
explicitly out of scope today.
"""

from accounts.models import User
from dashboard.services import DashboardService, BusinessInsightsService
from netsuite.repositories import NetSuiteConnectionRepository

def build_context(user: User) -> dict:
    connection_repository = NetSuiteConnectionRepository()
    connection = connection_repository.get_by_user(user)
    netsuite_connected = bool(connection and connection.is_active)

    business_context = None
    if netsuite_connected:
        dashboard_service = DashboardService()
        business_insights_service = BusinessInsightsService()
        business_context = {
            'summary': dashboard_service.get_summary(user=user),
            'recent_customers': dashboard_service.get_recent_customers(user=user),
            'recent_invoices': dashboard_service.get_recent_invoices(user=user),
            'recent_sales_orders': dashboard_service.get_recent_sales_orders(user=user),

            "sales_summary": business_insights_service.get_sales_summary(user=user),
            "top_customers": business_insights_service.get_top_customers(user=user),
            "overdue_invoices": business_insights_service.get_overdue_invoices(user=user),
            "inactive_vendors": business_insights_service.get_inactive_vendors(user=user),
            "low_inventory": business_insights_service.get_low_inventory(user=user),
        }

    return {
        'netsuite_connected': netsuite_connected,
        'business_context': business_context,
    }