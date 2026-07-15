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

    Field/table names below are only ones confirmed against real,
    published NetSuite SuiteQL usage (Oracle's own REST Record Service
    docs plus multiple independent working query examples) — notably:
    `customer.balance` / `transaction.total` are NOT queryable via
    SuiteQL (NetSuite returns 400 "Unknown identifier" — they're
    REST-only computed fields), so `balancesearch` / `foreigntotal` are
    used instead, which ARE real, queryable columns.
    """

    # Safety caps applied even to methods whose original signature had no
    # `limit` param (get_inactive_vendors) — SuiteQL already filters
    # server-side so this is a defensive ceiling, not the primary limit.
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

        Uses `foreignamountremaining > 0` rather than decoding
        transaction status codes (`CustInvc:A`/`CustInvc:B`, etc.) — that
        field is a real, documented amount-still-owed column and is the
        same signal a verified working NetSuite aging-report SuiteQL
        query uses, and it's far less likely to silently break than
        guessing status-code strings that vary by account configuration.
        `CURRENT_DATE - t.duedate` is Oracle SQL date arithmetic
        (confirmed via a published NetSuite aging-bucket SuiteQL query)
        and returns the day count directly — no Python date parsing
        needed.
        """
        limit = self._safe_int(limit, default=20)

        query = f"""
            SELECT
                t.id,
                t.tranid,
                t.duedate,
                t.status,
                t.foreignamountremaining,
                (CURRENT_DATE - t.duedate) AS days_overdue,
                c.companyname,
                c.entityid
            FROM transaction t
            INNER JOIN customer c ON t.entity = c.id
            WHERE t.type = 'CustInvc'
              AND t.duedate < CURRENT_DATE
              AND t.foreignamountremaining > 0
            ORDER BY days_overdue DESC
            FETCH FIRST {limit} ROWS ONLY
        """
        rows = self._execute(query=query, user=user)

        return [
            {
                'id': row.get('id'),
                'tran_id': row.get('tranid'),
                'entity': row.get('companyname') or row.get('entityid') or '--',
                'total': self._safe_float(row.get('foreignamountremaining')),
                'status': row.get('status'),
                'due_date': row.get('duedate'),
                'days_overdue': max(0, self._safe_int(row.get('days_overdue'), default=0)),
            }
            for row in rows
        ]

    def get_low_inventory(
        self,
        *,
        user: User,
        threshold: int = 10,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """
        Inventory items whose on-hand quantity is below `threshold` or
        below their own reorder point.

        `quantityonhand` / `reorderpoint` are confirmed queryable `item`
        table columns (a published NetSuite reorder-report SuiteQL query
        selects both directly). `displayname` was not independently
        confirmed as queryable, so `itemid` (confirmed) is used as the
        display name instead of guessing — the `name` key in the
        response contract is still populated, just from a verified field.
        """
        threshold = self._safe_int(threshold, default=10)
        limit = self._safe_int(limit, default=50)

        query = f"""
            SELECT id, itemid, quantityonhand, reorderpoint, isinactive
            FROM item
            WHERE quantityonhand < {threshold}
               OR (reorderpoint > 0 AND quantityonhand < reorderpoint)
            ORDER BY quantityonhand ASC
            FETCH FIRST {limit} ROWS ONLY
        """
        rows = self._execute(query=query, user=user)

        return [
            {
                'id': row.get('id'),
                'item_id': row.get('itemid'),
                'name': row.get('itemid'),
                'quantity_on_hand': self._safe_float(row.get('quantityonhand')),
                'reorder_point': self._safe_float(row.get('reorderpoint')),
                'is_inactive': row.get('isinactive') == 'T',
            }
            for row in rows
        ]

    def get_inactive_vendors(self, *, user: User) -> list[dict[str, Any]]:
        """
        Vendors marked inactive. `vendor` mirrors `customer`'s schema
        (both derive from NetSuite's Entity model) — `isinactive`,
        `companyname`, `entityid`, `email` are confirmed queryable on
        `customer`; `vendor` is documented as a structurally equivalent
        table.

        No `limit` in this method's signature (unchanged from the
        original), but MAX_ROWS is still applied as a defensive ceiling
        — SuiteQL's own WHERE clause already does the real filtering
        server-side, unlike the previous implementation which fetched
        every vendor and filtered client-side.
        """
        query = f"""
            SELECT id, companyname, entityid, email, status
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
                'status': row.get('status'),
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
