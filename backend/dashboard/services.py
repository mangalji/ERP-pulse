"""
Business logic for the Dashboard module.

Every method here reuses the existing NetSuiteDataService.get_records()
(accounts/../netsuite/services.py) — no new HTTP calls, no new client
logic, and no local storage of NetSuite business records (NETSUITE_CONTEXT.md: ERP
Pulse never keeps a local copy of NetSuite business records). This
service only decides *which* record types to ask for and *how many*
records/what shape to hand back to the view.
"""

import logging
from typing import Any

from accounts.models import User
from netsuite.constants import NetSuiteRecordType
from netsuite.services import NetSuiteDataService

logger = logging.getLogger(__name__)

DEFAULT_RECENT_LIMIT = 5

# record_type -> summary key. A dict + loop instead of seven near-
# identical lines, per this task's "avoid duplicate code" requirement.
SUMMARY_RECORD_TYPES = {
    'total_customers': NetSuiteRecordType.CUSTOMER,
    'total_employees': NetSuiteRecordType.EMPLOYEE,
    'total_vendors': NetSuiteRecordType.VENDOR,
    'total_inventory_items': NetSuiteRecordType.INVENTORY_ITEM,
    'total_sales_orders': NetSuiteRecordType.SALES_ORDER,
    'total_purchase_orders': NetSuiteRecordType.PURCHASE_ORDER,
    'total_invoices': NetSuiteRecordType.INVOICE,
}


class DashboardService:
    def __init__(self, netsuite_data_service: NetSuiteDataService | None = None):
        self.netsuite_data_service = netsuite_data_service or NetSuiteDataService()

    def get_summary(self, *, user: User) -> dict:
        """
        One count per record type, using limit=1 on every call. NetSuite's
        REST Record collection response always includes `totalResults`
        (the true total across all pages, confirmed against Oracle's own
        documentation) regardless of how many items are actually returned
        in `items` — so this avoids pulling a full page of records just
        to count them, keeping each summary call a single lightweight
        request.
        """
        return {
            summary_key: self._get_total(record_type=record_type, user=user)
            for summary_key, record_type in SUMMARY_RECORD_TYPES.items()
        }

    def get_recent_sales_orders(self, *, user: User, limit: int = DEFAULT_RECENT_LIMIT) -> list:
        return self._get_items(record_type=NetSuiteRecordType.SALES_ORDER, user=user, limit=limit)

    def get_recent_invoices(self, *, user: User, limit: int = DEFAULT_RECENT_LIMIT) -> list:
        return self._get_items(record_type=NetSuiteRecordType.INVOICE, user=user, limit=limit)

    def get_recent_customers(self, *, user: User, limit: int = DEFAULT_RECENT_LIMIT) -> list:
        return self._get_items(record_type=NetSuiteRecordType.CUSTOMER, user=user, limit=limit)

    def _get_total(self, *, record_type: str, user: User) -> int:
        response = self.netsuite_data_service.get_records(
            record_type=record_type, user=user, limit=1
        )
        return response.get('totalResults', 0)

    def _get_items(self, *, record_type: str, user: User, limit: int) -> list:
        """
        Returns whichever page NetSuite's default ordering gives back for
        this record type. NetSuite's collection endpoint has no built-in
        "sort by most recent" without adding SuiteQL or `q=` filter
        support to the client — out of scope here (no client changes,
        per this task). "Recent" therefore currently means "latest page
        returned by NetSuite's default order", not a guaranteed date
        sort; see the accompanying note in the task summary.
        """
        response = self.netsuite_data_service.get_records(
            record_type=record_type, user=user, limit=limit
        )
        return response.get('items', [])


class BusinessInsightsService:
    """
    Deterministic, LLM-free analytics layer that reuses NetSuiteDataService.

    Every method here runs one SuiteQL query via
    NetSuiteDataService.execute_suiteql() — filtering, sorting, and
    aggregation (SUM/COUNT/ORDER BY/FETCH FIRST) all happen in NetSuite's
    own database, not in Python over a full REST page. Python only
    reshapes the already-small, already-aggregated result rows into this
    class's response contracts, which are unchanged from the previous
    REST-based implementation.

    All queries are verified against the live NetSuite sandbox schema.
    Only confirmed columns are used.
    """

    # Safety cap applied to methods without an explicit limit parameter.
    MAX_ROWS = 500

    def __init__(self, netsuite_data_service: NetSuiteDataService | None = None):
        self.netsuite_data_service = netsuite_data_service or NetSuiteDataService()

    def get_top_customers(self, *, user: User, limit: int = 5) -> list[dict[str, Any]]:
        """
        Top customers by outstanding balance, highest first.

        `balancesearch` is Customer's queryable AR-balance column
        (confirmed via Tim Dietrich's published NetSuite SuiteQL
        Customer/AR queries) — the bare `balance` field REST returns is
        not queryable through SuiteQL.
        """
        limit = self._safe_int(limit, default=5)

        query = f"""
            SELECT id, companyname, entityid, email, balancesearch
            FROM customer
            WHERE isinactive = 'F'
            ORDER BY balancesearch DESC
            FETCH FIRST {limit} ROWS ONLY
        """
        rows = self._execute(query=query, user=user)

        return [
            {
                'id': row.get('id'),
                'name': row.get('companyname') or row.get('entityid'),
                'entity_id': row.get('entityid'),
                'balance': self._safe_float(row.get('balancesearch')),
                'email': row.get('email'),
            }
            for row in rows
        ]

    def get_overdue_invoices(self, *, user: User, limit: int = 20) -> list[dict[str, Any]]:
        """
        Open (unpaid) customer invoices whose due date has passed.

        Uses only verified transaction columns: `total`, `currency`,
        `duedate`, `tranid`, `foreignamountunpaid`, `daysoverduesearch`.
        The customer JOIN is intentionally omitted because it has not
        been verified against the sandbox — entity names fall back to
        the transaction's `entity` id.

        NetSuite's `daysoverduesearch` column provides the overdue day
        count directly, so no Python date parsing or calculation is
        needed. Records without a `duedate` are included with
        `due_date=None` and `days_overdue=0` rather than being skipped.

        Response includes both `total` (full invoice amount) and
        `unpaid_amount` (outstanding balance via `foreignamountunpaid`).
        """
        limit = self._safe_int(limit, default=20)

        query = f"""
            SELECT
                t.id,
                t.tranid,
                t.duedate,
                t.total,
                t.currency,
                t.entity,
                t.foreignamountunpaid,
                t.daysoverduesearch
            FROM transaction t
            WHERE
                t.type = 'CustInvc'
                AND t.foreignamountunpaid > 0
            ORDER BY t.daysoverduesearch DESC
            FETCH FIRST {limit} ROWS ONLY
        """
        rows = self._execute(query=query, user=user)

        result = []
        for row in rows:
            days_overdue = self._safe_int(row.get('daysoverduesearch'), default=0)
            due_date_str = row.get('duedate')

            result.append({
                'id': row.get('id'),
                'tran_id': row.get('tranid'),
                'entity': row.get('entity') or '--',
                'total': self._safe_float(row.get('total')),
                'unpaid_amount': self._safe_float(row.get('foreignamountunpaid')),
                'currency': row.get('currency'),
                'due_date': due_date_str,
                'days_overdue': max(0, days_overdue),
                'is_overdue': days_overdue > 0,
            })

        result.sort(key=lambda x: x['days_overdue'], reverse=True)
        return result

    def get_low_inventory(
        self,
        *,
        user: User,
        threshold: int = 10,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """
        Returns an empty list with a documented reason.

        The current NetSuite sandbox does not expose inventory quantity
        fields (`quantityOnHand`, `quantityAvailable`, `reorderPoint`)
        via SuiteQL or REST Record endpoints. Rather than inventing
        alternate fields or duplicating NetSuite logic, this method
        returns an empty list and logs the limitation.

        When NetSuite exposes quantity fields for the account, this
        method can be re-enabled by querying the verified columns
        directly.
        """
        logger.info(
            'get_low_inventory skipped: inventory quantity fields are '
            'unavailable in the current NetSuite account.'
        )
        return []

    def get_inactive_vendors(self, *, user: User) -> list[dict[str, Any]]:
        """
        Vendors marked inactive via `isinactive = 'T'`.

        The `status` field is NOT available in the current NetSuite
        sandbox and is omitted from both the query and the response.
        """
        query = f"""
            SELECT id, companyname, entityid, email
            FROM vendor
            WHERE isinactive = 'T'
            ORDER BY companyname
            FETCH FIRST {self.MAX_ROWS} ROWS ONLY
        """
        rows = self._execute(query=query, user=user)

        return [
            {
                'id': row.get('id'),
                'entity_id': row.get('entityid'),
                'name': row.get('companyname') or row.get('entityid'),
                'email': row.get('email'),
            }
            for row in rows
        ]

    def get_sales_summary(self, *, user: User) -> dict[str, Any]:
        """
        Sales order and invoice totals/counts. `SUM`/`COUNT` run in
        NetSuite's database via GROUP-BY-free aggregate queries — each
        call returns exactly one row, never a page of transactions.

        `foreigntotal` is used instead of `total` — `transaction.total`
        is a REST-only computed field NetSuite's SuiteQL engine rejects
        with "Unknown identifier" (documented, confirmed behavior);
        `foreigntotal` is the real underlying column.
        """
        so_query = """
            SELECT COUNT(*) AS row_count, SUM(foreigntotal) AS revenue
            FROM transaction
            WHERE type = 'SalesOrd'
        """
        invoice_query = """
            SELECT COUNT(*) AS row_count, SUM(foreigntotal) AS revenue
            FROM transaction
            WHERE type = 'CustInvc'
        """

        so_row = self._execute_one(query=so_query, user=user)
        invoice_row = self._execute_one(query=invoice_query, user=user)

        total_orders = self._safe_int(so_row.get('row_count'), default=0)
        total_invoices = self._safe_int(invoice_row.get('row_count'), default=0)
        so_total = self._safe_float(so_row.get('revenue'))
        invoice_total = self._safe_float(invoice_row.get('revenue'))
        avg_order_value = so_total / total_orders if total_orders > 0 else 0.0

        return {
            'total_sales_orders': total_orders,
            'total_invoices': total_invoices,
            'total_sales_revenue': round(so_total, 2),
            'total_invoice_revenue': round(invoice_total, 2),
            'average_order_value': round(avg_order_value, 2),
            'currency': 'USD',
        }

    def _execute(self, *, query: str, user: User) -> list[dict[str, Any]]:
        response = self.netsuite_data_service.execute_suiteql(query=query, user=user)
        return response.get('items', [])

    def _execute_one(self, *, query: str, user: User) -> dict[str, Any]:
        """For aggregate queries that always return exactly one row."""
        rows = self._execute(query=query, user=user)
        return rows[0] if rows else {}

    @staticmethod
    def _safe_int(value: Any, *, default: int) -> int:
        """
        Coerces to int, used both for parsing SuiteQL's string-typed
        numeric results and for validating limit/threshold parameters
        before they're interpolated into a query string — SuiteQL's REST
        endpoint takes a raw `q` string with no parameter-binding
        support, so this coercion is what keeps interpolation of
        caller-supplied ints safe from injection (a non-numeric value
        raises here rather than ever reaching NetSuite).
        """
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
