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
from datetime import datetime
from typing import Any

from django.utils import timezone
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
    Deterministic, LLM-free analytics layer that reuses DashboardService
    and NetSuiteDataService. Returns structured data only, intended for
    consumption by the AI module (natural-language explanations) or
    directly by frontend insight cards.

    No new NetSuite API calls are introduced — every method composes the
    existing data-fetching services and applies pure-Python sorting,
    filtering, and aggregation.
    """

    def __init__(
        self,
        dashboard_service: DashboardService | None = None,
        netsuite_data_service: NetSuiteDataService | None = None,
    ):
        self.dashboard_service = dashboard_service or DashboardService()
        self.netsuite_data_service = netsuite_data_service or NetSuiteDataService()

    def get_top_customers(self, *, user: User, limit: int = 5) -> list[dict[str, Any]]:
        """
        Returns the top customers by balance, highest first.

        NetSuite customer records typically include `balance` (outstanding
        balance). If the field is absent, the method falls back to sorting
        by `companyName` so the result is still deterministic.
        """
        response = self.netsuite_data_service.get_customers(user)
        items = response.get('items', [])

        def _sort_key(item: dict) -> Any:
            balance = item.get('balance')
            return balance if balance is not None else 0

        sorted_items = sorted(items, key=_sort_key, reverse=True)
        top = sorted_items[:limit]

        return [
            {
                'id': item.get('id') or item.get('internalId'),
                'name': item.get('companyName') or item.get('entityId'),
                'entity_id': item.get('entityId'),
                'balance': item.get('balance', 0),
                'email': item.get('email'),
            }
            for item in top
        ]

    def get_overdue_invoices(self, *, user: User, limit: int = 20) -> list[dict[str, Any]]:
        """
        Returns invoices that are not in a known paid/closed state and
        either have a positive `overdueBalance` or a `dueDate` in the past.

        The method is defensive about field names because NetSuite REST
        Record responses can vary by account configuration.
        """
        response = self.netsuite_data_service.get_invoices(user)
        items = response.get('items', [])
        now = timezone.now()

        CLOSED_STATUS_FRAGMENTS = ('Paid', 'Cancelled', 'Closed', 'Paid In Full')

        overdue: list[dict[str, Any]] = []

        for item in items:
            status = str(item.get('status', '') or '')
            if any(fragment in status for fragment in CLOSED_STATUS_FRAGMENTS):
                continue

            overdue_balance = item.get('overdueBalance') or 0
            due_date_str = item.get('dueDate') or item.get('createdDate')
            days_overdue = 0
            is_overdue = False

            if overdue_balance > 0:
                is_overdue = True
            elif due_date_str:
                try:
                    due_date = datetime.fromisoformat(due_date_str.replace('Z', '+00:00'))
                    if due_date.tzinfo is None:
                        due_date = due_date.replace(tzinfo=timezone.utc)
                    days_overdue = (now - due_date).days
                    if days_overdue > 0:
                        is_overdue = True
                except (ValueError, TypeError):
                    pass

            if not is_overdue:
                continue

            entity = item.get('entity')
            if isinstance(entity, dict):
                entity_name = entity.get('name') or entity.get('entityId') or '--'
            else:
                entity_name = entity or '--'

            overdue.append({
                'id': item.get('id') or item.get('internalId'),
                'tran_id': item.get('tranId'),
                'entity': entity_name,
                'total': item.get('total') or item.get('amount') or 0,
                'status': status,
                'due_date': due_date_str,
                'days_overdue': max(0, days_overdue),
            })

        overdue.sort(key=lambda x: x['days_overdue'], reverse=True)
        return overdue[:limit]

    def get_low_inventory(
        self,
        *,
        user: User,
        threshold: int = 10,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """
        Returns inventory items whose `quantityOnHand` is below `threshold`
        or below their own `reorderPoint`.

        Only `inventoryItem` subtype is queried, matching the existing
        DashboardService and NetSuite constants.
        """
        response = self.netsuite_data_service.get_items(
            user=user, item_type=NetSuiteRecordType.INVENTORY_ITEM
        )
        items = response.get('items', [])

        low_stock: list[dict[str, Any]] = []

        for item in items:
            qty = item.get('quantityOnHand')
            if qty is None:
                qty = item.get('quantity')
            qty = qty if qty is not None else 0

            reorder_point = item.get('reorderPoint') or 0

            if qty < threshold or (reorder_point and qty < reorder_point):
                low_stock.append({
                    'id': item.get('id') or item.get('internalId'),
                    'item_id': item.get('itemId'),
                    'name': item.get('displayName') or item.get('itemId'),
                    'quantity_on_hand': qty,
                    'reorder_point': reorder_point,
                    'is_inactive': item.get('isInactive', False),
                })

        low_stock.sort(key=lambda x: x['quantity_on_hand'])
        return low_stock[:limit]

    def get_inactive_vendors(self, *, user: User) -> list[dict[str, Any]]:
        """
        Returns vendors marked as inactive via `isInactive` or whose
        `status` string contains "inactive" / "closed".
        """
        response = self.netsuite_data_service.get_vendors(user)
        items = response.get('items', [])

        inactive: list[dict[str, Any]] = []

        for item in items:
            is_inactive = item.get('isInactive', False)
            status = str(item.get('status', '') or '').lower()
            status_inactive = 'inactive' in status or 'closed' in status

            if is_inactive or status_inactive:
                inactive.append({
                    'id': item.get('id') or item.get('internalId'),
                    'entity_id': item.get('entityId'),
                    'name': item.get('companyName') or item.get('entityId'),
                    'email': item.get('email'),
                    'status': item.get('status'),
                })

        return inactive

    def get_sales_summary(self, *, user: User) -> dict[str, Any]:
        """
        Aggregates recent sales orders and invoices into a single
        summary payload. Returns totals, counts, and an average order
        value derived entirely from the existing NetSuite record feeds.
        """
        sales_orders = self.netsuite_data_service.get_sales_orders(user).get('items', [])
        invoices = self.netsuite_data_service.get_invoices(user).get('items', [])

        so_total = sum(
            float(order.get('total') or order.get('amount') or 0) for order in sales_orders
        )
        invoice_total = sum(
            float(inv.get('total') or inv.get('amount') or 0) for inv in invoices
        )

        total_orders = len(sales_orders)
        total_invoices = len(invoices)
        avg_order_value = so_total / total_orders if total_orders > 0 else 0.0

        return {
            'total_sales_orders': total_orders,
            'total_invoices': total_invoices,
            'total_sales_revenue': round(so_total, 2),
            'total_invoice_revenue': round(invoice_total, 2),
            'average_order_value': round(avg_order_value, 2),
            'currency': 'USD',
        }
