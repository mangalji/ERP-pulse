"""
Analytics-domain tools.

Each tool wraps exactly one AnalyticsService method. No business logic
exists here — tools only delegate to the existing service.
"""

from typing import Any

from accounts.models import User
from ai.tools.base import SelfDescribingTool
from analytics.services import AnalyticsService


class TopCustomersTool(SelfDescribingTool):
    """Top customers by outstanding (AR) balance, highest first."""

    name = "get_top_customers"
    description = (
        "Returns the customers with the highest outstanding accounts-receivable "
        "(AR) balance — i.e. who owes the most money. Use this to answer "
        "'who are my biggest debtors?' or 'top customers by balance owed.'"
    )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Number of customers to return.",
                    "default": 5,
                },
            },
        }

    def execute(self, *, user: User, limit: int = 5, **kwargs) -> Any:
        service = AnalyticsService()
        return service.get_top_customers(user=user, limit=limit)


class OverdueInvoicesTool(SelfDescribingTool):
    """Open invoices past their due date, with days-overdue and unpaid amounts."""

    name = "get_overdue_invoices"
    description = (
        "Returns unpaid invoices whose due date has passed, including how "
        "many days overdue each one is and the unpaid amount. Use this to "
        "answer 'which invoices are overdue?' or 'show me late payments.'"
    )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Number of overdue invoices to return.",
                    "default": 20,
                },
            },
        }

    def execute(self, *, user: User, limit: int = 20, **kwargs) -> Any:
        service = AnalyticsService()
        return service.get_overdue_invoices(user=user, limit=limit)


class SalesSummaryTool(SelfDescribingTool):
    """Aggregated sales-order and invoice totals, counts, and averages."""

    name = "get_sales_summary"
    description = (
        "Returns aggregated sales-order and invoice metrics: total counts, "
        "total revenue, average order value, and average invoice value. "
        "Use this to answer 'what are my total sales?' or 'sales summary.'"
    )

    @property
    def parameters(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}}

    def execute(self, *, user: User, **kwargs) -> Any:
        service = AnalyticsService()
        return service.get_sales_summary(user=user)


class RevenueByCustomerTool(SelfDescribingTool):
    """Revenue grouped by customer, highest first."""

    name = "get_revenue_by_customer"
    description = (
        "Returns revenue totals grouped by customer, highest first. "
        "Defaults to invoiced revenue; pass transaction_type='SalesOrd' "
        "for booked-order values instead. Use this to answer 'who are my "
        "top customers by revenue?'"
    )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Number of customers to return.",
                    "default": 10,
                },
                "transaction_type": {
                    "type": "string",
                    "description": "Transaction type: 'CustInvc' (invoices) or 'SalesOrd' (sales orders).",
                    "default": "CustInvc",
                },
            },
        }

    def execute(self, *, user: User, limit: int = 10, transaction_type: str = "CustInvc", **kwargs) -> Any:
        service = AnalyticsService()
        return service.get_revenue_by_customer(user=user, limit=limit, transaction_type=transaction_type)


class RevenueForPeriodTool(SelfDescribingTool):
    """Revenue in a date range."""

    name = "get_revenue_for_period"
    description = (
        "Returns total revenue and transaction count for a half-open date "
        "range [start_date, end_date). Dates are YYYY-MM-DD strings. "
        "Defaults to invoiced revenue. Use this to answer 'what was my "
        "revenue last month?' or 'revenue between dates.'"
    )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "start_date": {
                    "type": "string",
                    "description": "Start date in YYYY-MM-DD format (inclusive).",
                },
                "end_date": {
                    "type": "string",
                    "description": "End date in YYYY-MM-DD format (exclusive).",
                },
                "transaction_type": {
                    "type": "string",
                    "description": "Transaction type: 'CustInvc' (invoices) or 'SalesOrd' (sales orders).",
                    "default": "CustInvc",
                },
            },
            "required": ["start_date", "end_date"],
        }

    def execute(self, *, user: User, start_date: str, end_date: str, transaction_type: str = "CustInvc", **kwargs) -> Any:
        service = AnalyticsService()
        return service.get_revenue_for_period(user=user, start_date=start_date, end_date=end_date, transaction_type=transaction_type)


class TotalReceivablesTool(SelfDescribingTool):
    """Total outstanding accounts receivable across all active customers."""

    name = "get_total_receivables"
    description = (
        "Returns the total outstanding accounts-receivable balance across "
        "all active customers and the number of customers with a balance. "
        "Use this to answer 'how much do customers owe me in total?'"
    )

    @property
    def parameters(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}}

    def execute(self, *, user: User, **kwargs) -> Any:
        service = AnalyticsService()
        return service.get_total_receivables(user=user)


class OverdueInvoicesSummaryTool(SelfDescribingTool):
    """Aggregated count and total amount of overdue invoices."""

    name = "get_overdue_invoices_summary"
    description = (
        "Returns the total count and total dollar amount of all overdue "
        "invoices — a summary without listing each invoice individually. "
        "Use this to answer 'how many invoices are overdue?' or 'total "
        "overdue amount.'"
    )

    @property
    def parameters(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}}

    def execute(self, *, user: User, **kwargs) -> Any:
        service = AnalyticsService()
        return service.get_overdue_invoices_summary(user=user)


class InactiveVendorsTool(SelfDescribingTool):
    """Vendors marked as inactive in NetSuite."""

    name = "get_inactive_vendors"
    description = (
        "Returns vendors that have been marked as inactive in NetSuite. "
        "Use this to answer 'which vendors are inactive?'"
    )

    @property
    def parameters(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}}

    def execute(self, *, user: User, **kwargs) -> Any:
        service = AnalyticsService()
        return service.get_inactive_vendors(user=user)


class SalesTrendByMonthTool(SelfDescribingTool):
    """Monthly sales-order and invoice-revenue trend."""

    name = "get_sales_trend_by_month"
    description = (
        "Returns month-by-month sales-order and invoice-revenue totals "
        "for the last N months, oldest first. Use this to answer 'show "
        "me the sales trend' or 'monthly revenue comparison' or 'explain "
        "the drop in order volume.'"
    )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "months": {
                    "type": "integer",
                    "description": "Number of months to include (1-24).",
                    "default": 6,
                },
            },
        }

    def execute(self, *, user: User, months: int = 6, **kwargs) -> Any:
        service = AnalyticsService()
        return service.get_sales_trend_by_month(user=user, months=months)


class ProductMarginsTool(SelfDescribingTool):
    """Top products by margin."""

    name = "get_product_margins"
    description = (
        "Returns the top products ranked by profit margin. "
        "Use this to answer 'what are my top products by margin?' or "
        "'show me product profitability.'"
    )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Number of products to return.",
                    "default": 10,
                },
            },
        }

    def execute(self, *, user: User, limit: int = 10, **kwargs) -> Any:
        service = AnalyticsService()
        return service.get_product_margins(user=user, limit=limit)


class CustomerChurnRiskTool(SelfDescribingTool):
    """Customers at risk of churning."""

    name = "get_customer_churn_risk"
    description = (
        "Returns customers who are at risk of churning based on their "
        "ordering patterns and activity. Use this to answer 'which customers "
        "are at risk of churning?' or 'show me customers who stopped ordering.'"
    )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Number of at-risk customers to return.",
                    "default": 10,
                },
            },
        }

    def execute(self, *, user: User, limit: int = 10, **kwargs) -> Any:
        service = AnalyticsService()
        return service.get_customer_churn_risk(user=user, limit=limit)

