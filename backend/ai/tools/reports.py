"""
Reports-domain tools.

Each tool wraps exactly one ReportsService method. No business logic
exists here — tools only delegate to the existing service.
"""

from typing import Any

from accounts.models import User
from ai.tools.base import SelfDescribingTool
from reports.services import ReportsService


class SalesTrendTool(SelfDescribingTool):
    """Monthly sales-trend report — thin pass-through to ReportsService."""

    name = "get_sales_trend"
    description = (
        "Returns the month-by-month sales trend (sales orders vs. invoice "
        "revenue) for the last N months. This delegates to the Reports "
        "module. Use this to answer 'get me a sales trend report' or "
        "'monthly sales report.'"
    )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "months": {
                    "type": "integer",
                    "description": "Number of months to include in the trend.",
                    "default": 6,
                },
            },
        }

    def execute(self, *, user: User, months: int = 6, **kwargs) -> Any:
        service = ReportsService()
        return service.get_sales_trend(user=user, months=months)

