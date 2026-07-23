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
