"""
Business logic for the Reports module — sales/revenue trend over time.

Like dashboard/services.py, every method here goes through
NetSuiteDataService.execute_suiteql() and returns computed results only;
no NetSuite business data (transactions, amounts) is ever stored locally
(NETSUITE_CONTEXT.md: ERP Pulse never keeps a local copy of NetSuite
business records). Reuses the exact SuiteQL shapes already
verified/used in dashboard/services.py's get_sales_summary() —
`foreigntotal` (not `total`, which SuiteQL rejects — see that file's
docstring), `type = 'SalesOrd'` / `'CustInvc'`, `transaction.trandate`.

The month-grouping GROUP BY TO_CHAR(trandate, 'YYYY-MM') / ADD_MONTHS
construct is new here and has not been confirmed against a live NetSuite
sandbox — please verify the exact output shape before relying on this in
production, same caveat dashboard/services.py already gives for its own
newer queries.
"""

import logging
from typing import Any

from accounts.models import User
from netsuite.services import NetSuiteDataService

logger = logging.getLogger(__name__)

DEFAULT_MONTHS = 6
MAX_MONTHS = 24


class ReportsService:
    def __init__(self, netsuite_data_service: NetSuiteDataService | None = None):
        self.netsuite_data_service = netsuite_data_service or NetSuiteDataService()

    def get_sales_trend(self, *, user: User, months: int = DEFAULT_MONTHS) -> dict[str, Any]:
        """
        Monthly sales-order and invoice-revenue totals for the last
        `months` months, oldest first — the shape a line/bar chart wants.

        Runs two GROUP BY queries (sales orders, invoices) rather than
        one query with a CASE-based pivot, mirroring get_sales_summary()'s
        existing "two separately-verified-shape queries" approach instead
        of introducing an unverified pivot construct.
        """
        months = self._safe_int(months, default=DEFAULT_MONTHS)
        months = max(1, min(months, MAX_MONTHS))

        so_rows = self._execute(query=self._monthly_query('SalesOrd', months), user=user)
        invoice_rows = self._execute(query=self._monthly_query('CustInvc', months), user=user)

        so_by_period = {row.get('period'): row for row in so_rows if row.get('period')}
        invoice_by_period = {row.get('period'): row for row in invoice_rows if row.get('period')}

        periods = sorted(set(so_by_period) | set(invoice_by_period))

        trend = [
            {
                'period': period,
                'sales_orders_total': round(self._safe_float(so_by_period.get(period, {}).get('revenue')), 2),
                'sales_orders_count': self._safe_int(so_by_period.get(period, {}).get('row_count'), default=0),
                'invoice_revenue_total': round(self._safe_float(invoice_by_period.get(period, {}).get('revenue')), 2),
                'invoice_count': self._safe_int(invoice_by_period.get(period, {}).get('row_count'), default=0),
            }
            for period in periods
        ]

        return {
            'months': months,
            'currency': 'USD',
            'trend': trend,
        }

    @staticmethod
    def _monthly_query(transaction_type: str, months: int) -> str:
        return f"""
            SELECT
                TO_CHAR(trandate, 'YYYY-MM') AS period,
                SUM(foreigntotal) AS revenue,
                COUNT(*) AS row_count
            FROM transaction
            WHERE type = '{transaction_type}'
                AND trandate >= ADD_MONTHS(TRUNC(SYSDATE), -{months})
            GROUP BY TO_CHAR(trandate, 'YYYY-MM')
            ORDER BY period
        """

    def _execute(self, *, query: str, user: User) -> list[dict[str, Any]]:
        response = self.netsuite_data_service.execute_suiteql(query=query, user=user)
        return response.get('items', [])

    @staticmethod
    def _safe_int(value: Any, *, default: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _safe_float(value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0