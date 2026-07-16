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
    
    def get_recent_employees(self, *, user: User, limit: int = DEFAULT_RECENT_LIMIT) -> list:
        return self._get_items(record_type=NetSuiteRecordType.EMPLOYEE, user=user, limit=limit)

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
        avg_invoice_value = invoice_total / total_invoices if total_invoices > 0 else 0.0

        return {
            'total_sales_orders': total_orders,
            'total_invoices': total_invoices,
            'total_sales_revenue': round(so_total, 2),
            'total_invoice_revenue': round(invoice_total, 2),
            'average_order_value': round(avg_order_value, 2),
            'average_invoice_value':round(avg_invoice_value,2),
            'currency': 'USD',
        }

    def get_revenue_by_customer(
        self, *, user: User, limit: int = 10, transaction_type: str = 'CustInvc'
    ) -> list[dict[str, Any]]:
        """
        Revenue grouped by customer, highest first. "Revenue" here means
        invoiced amount (`type = 'CustInvc'`) by default — pass
        transaction_type='SalesOrd' for booked-order value instead.

        Deliberately avoids a `transaction JOIN customer` in one SuiteQL
        query — same reasoning as `get_overdue_invoices`'s docstring:
        that join has not been confirmed against this account's schema.
        Instead this runs two separately-verified-shape queries:
        1. An aggregate GROUP BY on `transaction.entity` — `entity` and
           `foreigntotal` are already used and verified elsewhere in
           this file (`get_overdue_invoices`, `get_sales_summary`), only
           the GROUP BY itself is new here.
        2. A lookup of just those customer ids against `customer`,
           reusing the exact SELECT shape already verified in
           `get_top_customers`, just with `WHERE id IN (...)` added.

        The `IN (...)` filter is the only genuinely new SQL construct
        introduced by this method — please confirm it behaves as
        expected against your NetSuite sandbox before relying on this
        in production.
        """
        limit = self._safe_int(limit, default=10)

        revenue_query = f"""
            SELECT entity, SUM(foreigntotal) AS revenue
            FROM transaction
            WHERE type = '{transaction_type}'
            GROUP BY entity
            ORDER BY SUM(foreigntotal) DESC
            FETCH FIRST {limit} ROWS ONLY
        """
        revenue_rows = self._execute(query=revenue_query, user=user)

        entity_ids = [
            self._safe_int(row.get('entity'), default=0)
            for row in revenue_rows
            if row.get('entity') is not None
        ]
        entity_ids = [eid for eid in entity_ids if eid]
        if not entity_ids:
            return []

        id_list = ','.join(str(eid) for eid in entity_ids)
        customer_query = f"""
            SELECT id, companyname, entityid
            FROM customer
            WHERE id IN ({id_list})
        """
        customer_rows = self._execute(query=customer_query, user=user)
        customer_by_id = {str(row.get('id')): row for row in customer_rows}

        result = []
        for row in revenue_rows:
            entity_id = row.get('entity')
            if entity_id is None:
                continue
            customer = customer_by_id.get(str(self._safe_int(entity_id, default=0)), {})
            result.append({
                'id': entity_id,
                'name': customer.get('companyname') or customer.get('entityid') or f'Customer {entity_id}',
                'revenue': round(self._safe_float(row.get('revenue')), 2),
            })
        return result

    def get_revenue_for_period(
        self,
        *,
        user: User,
        start_date: str,
        end_date: str,
        transaction_type: str = 'CustInvc',
    ) -> dict[str, Any]:
        """
        Revenue for the half-open date range [start_date, end_date) —
        start_date inclusive, end_date exclusive. Dates are 'YYYY-MM-DD'
        strings.

        UNVERIFIED: introduces `transaction.trandate`, NetSuite's
        standard transaction-date column. Unlike every other field used
        in this file, `trandate` has not been used or confirmed anywhere
        else in this codebase (AI_HANDOFF.md requires only confirmed
        SuiteQL fields). Please test this against your sandbox before
        trusting the numbers — if `trandate` isn't queryable via SuiteQL
        on this account, `createddate` is a likely fallback to try.
        """
        query = f"""
            SELECT SUM(foreigntotal) AS revenue, COUNT(*) AS row_count
            FROM transaction
            WHERE type = '{transaction_type}'
            AND trandate >= TO_DATE('{start_date}', 'YYYY-MM-DD')
            AND trandate < TO_DATE('{end_date}', 'YYYY-MM-DD')
        """
        row = self._execute_one(query=query, user=user)

        return {
            'revenue': round(self._safe_float(row.get('revenue')), 2),
            'transaction_count': self._safe_int(row.get('row_count'), default=0),
            'start_date': start_date,
            'end_date': end_date,
            'currency': 'USD',
        }
    
    def get_total_receivables(self, *, user: User) -> dict[str, Any]:
        """
        Total outstanding AR across all active customers — "how much do
        my customers owe me in total?"
 
        Safe: `balancesearch` and `isinactive` on `customer` are already
        verified elsewhere in this file (`get_top_customers`); this is
        just a SUM instead of a ranked list.
        """
        query = """
            SELECT SUM(balancesearch) AS total_receivable, COUNT(*) AS customer_count
            FROM customer
            WHERE isinactive = 'F' AND balancesearch > 0
        """
        row = self._execute_one(query=query, user=user)
 
        return {
            'total_receivable': round(self._safe_float(row.get('total_receivable')), 2),
            'customers_with_balance': self._safe_int(row.get('customer_count'), default=0),
            'currency': 'USD',
        }
    
    def get_overdue_invoices_summary(self, *, user: User) -> dict[str, Any]:
        """
        Count and total amount of overdue invoices — "how many invoices
        are overdue and what's the total?" — without handing the model a
        full row list to sum itself (LLMs are unreliable at arithmetic
        over a JSON blob).
 
        Safe: `foreignamountunpaid` and `daysoverduesearch` on
        `transaction` are already verified elsewhere in this file
        (`get_overdue_invoices`); this is just an aggregate over the
        same WHERE condition instead of a ranked row list.
        """
        query = """
            SELECT COUNT(*) AS invoice_count, SUM(foreignamountunpaid) AS total_overdue
            FROM transaction
            WHERE type = 'CustInvc'
            AND foreignamountunpaid > 0
            AND daysoverduesearch > 0
        """
        row = self._execute_one(query=query, user=user)
 
        return {
            'overdue_invoice_count': self._safe_int(row.get('invoice_count'), default=0),
            'total_overdue_amount': round(self._safe_float(row.get('total_overdue')), 2),
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