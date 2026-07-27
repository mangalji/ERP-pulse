"""
Dashboard-domain tools.

Each tool wraps exactly one DashboardService method. No business logic
exists here — tools only delegate to the existing service.
"""

from typing import Any

from accounts.models import User
from ai.tools.base import SelfDescribingTool
from dashboard.services import DashboardService


class DashboardSummaryTool(SelfDescribingTool):
    """Record-type counts for the dashboard summary."""

    name = "get_dashboard_summary"
    description = (
        "Returns a summary of record-type counts from NetSuite: total "
        "customers, employees, vendors, inventory items, sales orders, "
        "purchase orders, and invoices. Use this to answer 'what's on "
        "my dashboard?' or 'give me a business overview.'"
    )

    @property
    def parameters(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}}

    def execute(self, *, user: User, **kwargs) -> Any:
        service = DashboardService()
        return service.get_summary(user=user)


class RecentSalesOrdersTool(SelfDescribingTool):
    """Most recent sales orders."""

    name = "get_recent_sales_orders"
    description = (
        "Returns the most recent sales orders from NetSuite. Use this to "
        "answer 'show recent sales orders' or 'latest orders.'"
    )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Number of sales orders to return.",
                    "default": 5,
                },
            },
        }

    def execute(self, *, user: User, limit: int = 5, **kwargs) -> Any:
        service = DashboardService()
        return service.get_recent_sales_orders(user=user, limit=limit)


class RecentInvoicesTool(SelfDescribingTool):
    """Most recent invoices."""

    name = "get_recent_invoices"
    description = (
        "Returns the most recent invoices from NetSuite. Use this to "
        "answer 'show recent invoices' or 'latest invoices.'"
    )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Number of invoices to return.",
                    "default": 5,
                },
            },
        }

    def execute(self, *, user: User, limit: int = 5, **kwargs) -> Any:
        service = DashboardService()
        return service.get_recent_invoices(user=user, limit=limit)


class RecentCustomersTool(SelfDescribingTool):
    """Most recent customers."""

    name = "get_recent_customers"
    description = (
        "Returns the most recent customers from NetSuite. Use this to "
        "answer 'show recent customers' or 'latest customers added.'"
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
        service = DashboardService()
        return service.get_recent_customers(user=user, limit=limit)


class RecentEmployeesTool(SelfDescribingTool):
    """Most recent employees."""

    name = "get_recent_employees"
    description = (
        "Returns the most recent employees from NetSuite. Use this to "
        "answer 'show recent employees' or 'latest employees added.'"
    )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Number of employees to return.",
                    "default": 5,
                },
            },
        }

    def execute(self, *, user: User, limit: int = 5, **kwargs) -> Any:
        service = DashboardService()
        return service.get_recent_employees(user=user, limit=limit)

