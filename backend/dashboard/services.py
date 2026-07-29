"""
Business logic for the Dashboard module.

Every method here reuses the existing NetSuiteDataService.get_records()
(accounts/../netsuite/services.py) — no new HTTP calls, no new client
logic, and no local storage of NetSuite business records (NETSUITE_CONTEXT.md: ERP
Pulse never keeps a local copy of NetSuite business records). This
service only decides *which* record types to ask for and *how many*
records/what shape to hand back to the view.

Note (Phase 3 — Analytics & AI Architecture): KPI/business-insight
calculations (top customers, overdue invoices, sales summary, revenue
by period, etc.) previously lived here as `BusinessInsightsService` and
have moved to analytics/services.py as `AnalyticsService`, since
Reports and AI both need that logic too and neither should import from
a presentation-oriented app like `dashboard`. This file now contains
only the simple record-count/recent-record logic the dashboard summary
view itself needs.
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
# Map summary keys to SuiteQL-based list methods on NetSuiteDataService.
# Entity list pages (CustomersPage, VendorsPage, etc.) use these same
# methods, so the dashboard counts will always match what users see in
# the list views — unlike the REST Record API (get_records) which can
# return different totals than SuiteQL for the same data.
SUMMARY_RECORD_TYPES = {
    'total_customers': ('list_customers', NetSuiteRecordType.CUSTOMER),
    'total_employees': ('list_employees', NetSuiteRecordType.EMPLOYEE),
    'total_vendors': ('list_vendors', NetSuiteRecordType.VENDOR),
    'total_inventory_items': ('list_inventory_items', NetSuiteRecordType.INVENTORY_ITEM),
    'total_sales_orders': ('list_sales_orders', NetSuiteRecordType.SALES_ORDER),
    'total_purchase_orders': ('list_purchase_orders', NetSuiteRecordType.PURCHASE_ORDER),
    'total_invoices': ('list_invoices', NetSuiteRecordType.INVOICE),
}


class DashboardService:
    def __init__(self, netsuite_data_service: NetSuiteDataService | None = None):
        self.netsuite_data_service = netsuite_data_service or NetSuiteDataService()

    def get_summary(self, *, user: User) -> dict:
        """
        One count per record type, using limit=1 on every call. Uses the
        same SuiteQL-based list methods that the entity list pages
        (CustomersPage, VendorsPage, etc.) call, so dashboard KPI counts
        always match what users see on those pages. Each call fetches 1
        record; NetSuite's SuiteQL response always includes `totalResults`
        (the true total across all pages), keeping each summary call
        lightweight.
        """
        return {
            summary_key: self._get_total(
                method_name=method_name, record_type=record_type, user=user,
            )
            for summary_key, (method_name, record_type) in SUMMARY_RECORD_TYPES.items()
        }

    def get_recent_sales_orders(self, *, user: User, limit: int = DEFAULT_RECENT_LIMIT) -> list:
        return self._get_items(record_type=NetSuiteRecordType.SALES_ORDER, user=user, limit=limit)

    def get_recent_invoices(self, *, user: User, limit: int = DEFAULT_RECENT_LIMIT) -> list:
        return self._get_items(record_type=NetSuiteRecordType.INVOICE, user=user, limit=limit)

    def get_recent_customers(self, *, user: User, limit: int = DEFAULT_RECENT_LIMIT) -> list:
        return self._get_items(record_type=NetSuiteRecordType.CUSTOMER, user=user, limit=limit)
    
    def get_recent_employees(self, *, user: User, limit: int = DEFAULT_RECENT_LIMIT) -> list:
        return self._get_items(record_type=NetSuiteRecordType.EMPLOYEE, user=user, limit=limit)

    def _get_total(self, *, method_name: str, record_type: str, user: User) -> int:
        """
        Fetch exactly 1 record and return totalResults.

        Uses the SuiteQL-based list method (matching the entity list pages)
        for accuracy. If the SuiteQL call fails (e.g. a field name mismatch
        for this account), falls back to the REST Record API which is more
        broadly supported. Logs the failure for diagnostics.
        """
        list_method = getattr(self.netsuite_data_service, method_name, None)
        if list_method is not None:
            try:
                response = list_method(user=user, limit=1, offset=0)
                return response.get('totalResults', 0)
            except Exception as exc:
                logger.warning(
                    'Dashboard summary: %s failed via SuiteQL — falling back to REST API. '
                    'Error: %s', method_name, exc,
                )

        # Fallback: REST Record API (always available, may differ from
        # SuiteQL totals for some record types).
        try:
            response = self.netsuite_data_service.get_records(
                record_type=record_type, user=user, limit=1,
            )
            return response.get('totalResults', 0)
        except Exception as exc:
            logger.exception(
                'Dashboard summary: %s (REST fallback) also failed for user %s — %s',
                method_name, user.id, exc,
            )
            return 0

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
