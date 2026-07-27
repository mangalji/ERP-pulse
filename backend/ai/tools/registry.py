"""
Tool Registry — discovers, registers, and executes tools.

The registry is intentionally a flat list, not a large switch/if-else
statement. Tools register themselves here by being listed in the
TOOL_CLASSES tuple; to add a new tool, import its class and add it to
that tuple. No other code in this file changes.

Responsibilities:
1. Discover — know which tools exist.
2. Register — make them available by name.
3. Execute — run the right tool given its name + args.
"""

from typing import Any

from accounts.models import User
from ai.tools.analytics import (
    InactiveVendorsTool,
    OverdueInvoicesSummaryTool,
    OverdueInvoicesTool,
    RevenueByCustomerTool,
    RevenueForPeriodTool,
    SalesSummaryTool,
    SalesTrendByMonthTool,
    TopCustomersTool,
    TotalReceivablesTool,
)
from ai.tools.base import SelfDescribingTool
from ai.tools.dashboard import (
    DashboardSummaryTool,
    RecentCustomersTool,
    RecentEmployeesTool,
    RecentInvoicesTool,
    RecentSalesOrdersTool,
)
from ai.tools.reports import SalesTrendTool

# Register all tool classes here. Adding a new tool means importing its
# class and adding it to this tuple — nothing else in this file changes.
TOOL_CLASSES = (
    # Analytics
    TopCustomersTool,
    OverdueInvoicesTool,
    SalesSummaryTool,
    RevenueByCustomerTool,
    RevenueForPeriodTool,
    TotalReceivablesTool,
    OverdueInvoicesSummaryTool,
    InactiveVendorsTool,
    SalesTrendByMonthTool,
    # Dashboard
    DashboardSummaryTool,
    RecentSalesOrdersTool,
    RecentInvoicesTool,
    RecentCustomersTool,
    RecentEmployeesTool,
    # Reports
    SalesTrendTool,
)


class ToolRegistry:
    """
    Discovers, registers, and executes tools.

    Usage::

        registry = ToolRegistry()
        registry.list_descriptions()   # -> [{"name": ..., "description": ..., "parameters": ...}, ...]
        result = registry.execute("get_top_customers", user=user, limit=5)
    """

    def __init__(self):
        self._tools: dict[str, SelfDescribingTool] = {}
        self._discover()

    def _discover(self) -> None:
        """Instantiate and index every tool class from TOOL_CLASSES, keyed by name."""
        for tool_cls in TOOL_CLASSES:
            tool = tool_cls()
            self._tools[tool.name] = tool

    def get_tool(self, name: str) -> SelfDescribingTool | None:
        """Look up a tool by its name. Returns None if not found."""
        return self._tools.get(name)

    def list_tools(self) -> list[SelfDescribingTool]:
        """Return all registered tool instances."""
        return list(self._tools.values())

    def list_descriptions(self) -> list[dict[str, Any]]:
        """
        Return metadata for every registered tool — used by the Planner
        to decide which tools a question needs.

        Each entry contains ``name``, ``description``, and ``parameters``
        (JSON Schema), matching what SelfDescribingTool exposes.
        """
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
            }
            for tool in self.list_tools()
        ]

    def execute(self, *, name: str, user: User, **kwargs) -> Any:
        """
        Execute a tool by name.

        Args:
            name: The tool's unique name (e.g. ``"get_top_customers"``).
            user: The requesting user.
            **kwargs: Parameters forwarded to the tool's ``execute()``.

        Returns:
            The raw output from the underlying service method.

        Raises:
            KeyError: If no tool is registered with ``name``.
        """
        tool = self.get_tool(name)
        if tool is None:
            raise KeyError(f"Unknown tool: '{name}'. Available: {list(self._tools.keys())}")
        return tool.execute(user=user, **kwargs)

