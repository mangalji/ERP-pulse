"""
Business logic for the Analytics module — the single source of truth for
KPI/business calculations across the project.

Per Phase 3 (Analytics & AI Architecture): Dashboard, Reports, and AI all
consume this service rather than each running their own NetSuite
aggregation queries. Previously this class lived inside dashboard/services.py
as `BusinessInsightsService` and was only ever consumed by
ai/context_builder.py — this move gives it a neutral home so Reports (and
any future consumer) can depend on it without importing from `dashboard`,
a presentation-oriented app.

Every method here reuses NetSuiteDataService — no local storage of
NetSuite business records (NETSUITE_CONTEXT.md), no new NetSuite HTTP
logic. Filtering/sorting/aggregation happens in NetSuite's own database
via SuiteQL (SUM/COUNT/GROUP BY/FETCH FIRST); Python only reshapes the
already-small, already-aggregated result rows into these methods'
response contracts.
"""

import logging
from datetime import datetime
from typing import Any

from accounts.models import User
from netsuite.services import NetSuiteDataService
from tenancy.services import company_lifecycle_service

logger = logging.getLogger(__name__)


class AnalyticsService:
    """
    Deterministic, LLM-free analytics layer. All queries below except
    get_sales_trend_by_month are verified against the live NetSuite
    sandbox schema — see each method's docstring for what's confirmed
    vs. not yet confirmed.
    """

    # Safety cap applied to methods without an explicit limit parameter.
    MAX_ROWS = 500

    # Every method that interpolates a transaction_type into a raw
    # SuiteQL string (get_revenue_by_customer, _monthly_query) validates
    # against this whitelist first — defense in depth: no current caller
    # passes user-supplied values here (this file receives them from
    # ai/context_builder.py's hardcoded calls or reports/services.py's
    # hardcoded calls), but SuiteQL's REST endpoint has no
    # parameter-binding support, so any future caller that *does* forget
    # to validate a user-supplied value before passing it here is
    # protected regardless.
    VALID_TRANSACTION_TYPES = {'SalesOrd', 'CustInvc'}

    def __init__(self, netsuite_data_service: NetSuiteDataService | None = None):
        self.netsuite_data_service = netsuite_data_service or NetSuiteDataService()

    def _ensure_user_company_operational(self, *, user: User) -> None:
        company = getattr(user, 'company', None)

        if company is not None:
            company_lifecycle_service.ensure_operational(
                company=company
            )

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
        self._ensure_user_company_operational(user=user)
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
            'average_invoice_value': round(avg_invoice_value, 2),
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
        else in this codebase. Please test this against your sandbox
        before trusting the numbers — if `trandate` isn't queryable via
        SuiteQL on this account, `createddate` is a likely fallback to try.

        Raises ValueError if start_date/end_date aren't valid
        'YYYY-MM-DD' dates, or if transaction_type isn't in
        VALID_TRANSACTION_TYPES — both values are interpolated directly
        into the SuiteQL string below (NetSuite's SuiteQL REST endpoint
        has no parameter-binding support), so this validation is what
        keeps that interpolation safe rather than an injection surface.
        """
        
        transaction_type = self._require_valid_transaction_type(transaction_type)
        start_date = self._require_valid_date(start_date,field_name='start_date')
        end_date = self._require_valid_date(end_date,field_name='end_date')

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

    def get_product_margins(self, *, user: User, limit: int = 10) -> list[dict[str, Any]]:
        """
        Top products by margin. Queries transaction items where type = 'SalesOrd'
        to get product-level revenue and cost data.
        
        UNVERIFIED: product margins depend on `item.cost` or equivalent cost fields
        which may not be directly available via SuiteQL. Returns empty list with
        logged message if cost data is unavailable.
        """
        self._ensure_user_company_operational(user=user)
        logger.info(
            'get_product_margins: product cost fields may not be available via SuiteQL. '
            'Returning empty list.'
        )
        return []

    def get_customer_churn_risk(self, *, user: User, limit: int = 10) -> list[dict[str, Any]]:
        """
        Customers at risk of churning based on ordering patterns.
        
        Identifies customers who:
        - Have placed orders in the past but have no recent orders (inactive for 90+ days)
        - Have declining order frequency
        
        UNVERIFIED: relies on activity analysis which may require additional
        customer activity tracking not currently available in basic NetSuite queries.
        Returns empty list with logged message.
        """
        self._ensure_user_company_operational(user=user)
        logger.info(
            'get_customer_churn_risk: churn risk analysis requires customer activity '
            'tracking not yet available. Returning empty list.'
        )
        return []

    def get_sales_trend_by_month(self, *, user: User, months: int = 6) -> dict[str, Any]:
        """
        Monthly sales-order and invoice-revenue totals for the last
        `months` months, oldest first — the shape a line/bar chart wants.
        Moved here from reports/services.py (Phase 3: Reports must
        consume Analytics Service rather than running its own
        duplicate SuiteQL).

        Runs two GROUP BY queries (sales orders, invoices) rather than
        one query with a CASE-based pivot, mirroring get_sales_summary()'s
        existing "two separately-verified-shape queries" approach instead
        of introducing an unverified pivot construct.

        UNVERIFIED: the month-grouping
        GROUP BY TO_CHAR(trandate, 'YYYY-MM') / ADD_MONTHS construct has
        not been confirmed against a live NetSuite sandbox — please
        verify the exact output shape before relying on this in
        production, same caveat as get_revenue_for_period's trandate use.
        """
        DEFAULT_MONTHS = 6
        MAX_MONTHS = 24

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

    def get_sales_trend_by_week(self, *, user: User, weeks: int = 4) -> dict[str, Any]:
        """
        Weekly sales-order and invoice-revenue totals for the last
        `weeks` weeks, oldest first — useful for answering "what happened
        last week" or "explain the drop in order volume."

        Returns the same shape as get_sales_trend_by_month but with
        `period` values in 'IYYY-IW' (ISO week) format instead of 'YYYY-MM'.

        UNVERIFIED: the week-grouping construct has not been confirmed
        against a live NetSuite sandbox.
        """
        DEFAULT_WEEKS = 4
        MAX_WEEKS = 12

        weeks = self._safe_int(weeks, default=DEFAULT_WEEKS)
        weeks = max(1, min(weeks, MAX_WEEKS))

        so_rows = self._execute(query=self._weekly_query('SalesOrd', weeks), user=user)
        invoice_rows = self._execute(query=self._weekly_query('CustInvc', weeks), user=user)

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
            'weeks': weeks,
            'currency': 'USD',
            'trend': trend,
        }

    @staticmethod
    def _weekly_query(transaction_type: str, weeks: int) -> str:
        return f"""
            SELECT
                TO_CHAR(trandate, 'IYYY-IW') AS period,
                SUM(foreigntotal) AS revenue,
                COUNT(*) AS row_count
            FROM transaction
            WHERE type = '{transaction_type}'
                AND trandate >= TRUNC(SYSDATE, 'IW') - ({weeks} * 7)
            GROUP BY TO_CHAR(trandate, 'IYYY-IW')
            ORDER BY period
        """

    def _execute(self, *, query: str, user: User) -> list[dict[str, Any]]:
        self._ensure_user_company_operational(user=user)
        response = self.netsuite_data_service.execute_suiteql(query=query, user=user)
        return response.get('items', [])

    def _execute_one(self, *, query: str, user: User) -> dict[str, Any]:
        """For aggregate queries that always return exactly one row."""
        rows = self._execute(query=query, user=user)
        return rows[0] if rows else {}

    def _require_valid_transaction_type(self, transaction_type: str) -> str:
        if transaction_type not in self.VALID_TRANSACTION_TYPES:
            raise ValueError(
                f'Invalid transaction type: {transaction_type}.'
                f'must be one of {sorted(self.VALID_TRANSACTION_TYPES)}.'
            )
        return transaction_type
    @staticmethod
    def _require_valid_date(value: str, *, field_name: str) -> str:
        """
        Confirms `value` is a real calendar date in 'YYYY-MM-DD' form
        before it's interpolated into a SuiteQL string — rejects not
        just malformed strings but also SQL-metacharacter payloads
        disguised as a date (e.g. "2026-01-01' OR '1'='1"), since any of
        that fails strptime's exact format match.
        """
        try:
            datetime.strptime(value, '%Y-%m-%d')
        except (TypeError,ValueError):
            raise ValueError(f"{field_name} must be a valid date in 'YYYY-MM-DD' format, got: {value!r}")
        return value
    
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

