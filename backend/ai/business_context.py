"""
Business Context objects (Phase 3 — Analytics & AI Architecture:
"Introduce Business Context objects").

Wraps the shape ai/context_builder.py has always assembled in a typed
dataclass instead of a bare dict — callers (ai/services.py,
ai/prompts.py) now get real attributes instead of stringly-typed dict
keys, catching a typo'd field name at development time instead of
silently returning None from a mistyped .get() call.

What's actually collected (which services are called, graceful
degradation on failure) is unchanged — this file only defines the
shape; context_builder.py still does the assembling.
"""

from dataclasses import asdict, dataclass
from typing import Any, Optional

@dataclass
class BusinessContext:
    """
    Populated only when the user has an active NetSuite connection.
    Every field is Optional because context_builder._safe_call() sets a
    field to None (rather than omitting it or raising) when that
    specific section fails to build — this preserves the existing
    "degrade one section, not the whole request" behavior exactly.
    """

    summary: Optional[dict] = None
    recent_customers: Optional[list] = None
    recent_invoices: Optional[list] = None
    recent_sales_orders: Optional[list] = None
    recent_employees: Optional[list] = None

    sales_summary: Optional[dict] = None
    top_customers: Optional[list] = None
    overdue_invoices: Optional[list] = None
    overdue_invoices_summary: Optional[dict] = None
    inactive_vendors: Optional[list] = None
    low_inventory: Optional[list] = None
    total_receivables: Optional[dict] = None

    top_customers_by_revenue: Optional[list] = None
    revenue_this_month: Optional[dict] = None
    revenue_last_month: Optional[dict] = None
    revenue_this_fiscal_year: Optional[dict] = None

    sales_trend: Optional[dict] = None
    product_margins: Optional[dict] = None
    customer_churn_risk: Optional[dict] = None

    def as_dict(self) -> dict[str,Any]:
        """For ai/prompts.py's json.dumps(...) call — same shape the old bare dict had."""
        return asdict(self)
    
@dataclass
class AIRequestContext:
    """Top-level object returned by context_builder.build_context()."""

    netsuite_connected: bool
    business_context: Optional[BusinessContext] = None

    def as_dict(self) -> dict[str,Any]:
        return {
            'netsuite_connected': self.netsuite_connected,
            'business_context': self.business_context.as_dict() if self.business_context else None,
        }