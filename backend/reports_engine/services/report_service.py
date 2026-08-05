"""
Report generation services.

A ``ReportFactory`` maps each report type to a dedicated report service.
Every report service reuses the existing BI services (SummaryService,
SalesService, PurchaseService, CustomerService, InventoryService,
FinanceService, DashboardService, AnalyticsService) and local models —
never duplicating KPI calculations. Each service returns a normalized
``{ headers, rows }`` payload that the generic ExportService can render
to any format.
"""

from __future__ import annotations

import logging
from typing import Any

from accounts.models import User
from ai.models import AIAuditLog
from bi.services import (
    CustomerService,
    FinanceService,
    InventoryService,
    PurchaseService,
    SalesService,
    SummaryService,
)
from bi.utils.date_ranges import resolve_date_range
from dashboard.services import DashboardService
from invoice.models import FileStatus, InvoiceBatch
from ocr.models import OCRUpload
from reports_engine.models import ReportType
from sync.models import SyncRun

logger = logging.getLogger(__name__)


class BaseReportService:
    """Shared helpers for all report services."""

    report_type = None

    def __init__(self):
        self.dashboard = DashboardService()

    def resolve(self, **filters) -> dict:
        return resolve_date_range(**filters)

    def _company(self, user: User):
        return getattr(user, 'company', None)

    def _payload(self, *, headers: list[str], rows: list[list[Any]], summary: dict | None = None) -> dict:
        return {
            'report_type': self.report_type,
            'headers': headers,
            'rows': rows,
            'summary': summary or {},
        }


class SalesReportService(BaseReportService):
    """Sales report — reuses BI SalesService."""

    report_type = ReportType.SALES

    def generate(self, *, user: User, **filters) -> dict:
        data = SalesService().get_sales(user=user, **filters)
        headers = ['Period', 'Sales Orders', 'Sales Revenue', 'Invoice Revenue', 'Avg Order Value']
        rows = []
        for row in data.get('trend', []):
            rows.append([
                row.get('period'),
                row.get('sales_orders_count'),
                row.get('sales_orders_total'),
                row.get('invoice_revenue_total'),
                '',
            ])
        summary = {
            'currency': data.get('currency', 'USD'),
            'change_pct': data.get('change_pct'),
            'window': data.get('window'),
        }
        return self._payload(headers=headers, rows=rows, summary=summary)


class PurchaseReportService(BaseReportService):
    """Purchase report — reuses BI PurchaseService."""

    report_type = ReportType.PURCHASE

    def generate(self, *, user: User, **filters) -> dict:
        data = PurchaseService().get_purchase(user=user, **filters)
        headers = ['Transaction ID', 'Entity', 'Status', 'Total', 'Date']
        rows = [
            [
                o.get('tranId'),
                (o.get('entity') or {}).get('name') if isinstance(o.get('entity'), dict) else o.get('entity'),
                o.get('status'),
                o.get('total'),
                o.get('createdDate'),
            ]
            for o in data.get('recent_orders', [])
        ]
        summary = {
            'total_purchase_orders': data.get('total_purchase_orders'),
            'total_spend': data.get('total_spend'),
            'average_order_value': data.get('average_order_value'),
            'currency': data.get('currency', 'USD'),
        }
        return self._payload(headers=headers, rows=rows, summary=summary)


class CustomerReportService(BaseReportService):
    """Customer report — reuses BI CustomerService."""

    report_type = ReportType.CUSTOMER

    def generate(self, *, user: User, **filters) -> dict:
        data = CustomerService().get_customers(user=user, **filters)
        headers = ['Customer', 'Revenue', 'Balance', 'Entity ID']
        rows = []
        revenue_by = {c.get('name'): c.get('revenue') for c in data.get('revenue_by_customer', []) if c.get('name')}
        for c in data.get('top_customers', []):
            name = c.get('name')
            rows.append([
                name,
                revenue_by.get(name, 0),
                c.get('balance'),
                c.get('entity_id'),
            ])
        summary = {
            'total_receivables': data.get('total_receivables', {}).get('total_receivable'),
            'currency': data.get('currency', 'USD'),
        }
        return self._payload(headers=headers, rows=rows, summary=summary)


class VendorReportService(BaseReportService):
    """Vendor report — reuses AnalyticsService.get_inactive_vendors + DashboardService."""

    report_type = ReportType.VENDOR

    def generate(self, *, user: User, **filters) -> dict:
        from analytics.services import AnalyticsService
        analytics = AnalyticsService()
        try:
            vendors = analytics.get_inactive_vendors(user=user)
        except Exception as exc:
            logger.warning('Vendor report failed: %s', exc)
            vendors = []
        headers = ['Vendor', 'Entity ID', 'Email']
        rows = [[v.get('name'), v.get('entity_id'), v.get('email')] for v in vendors]
        try:
            total_vendors = self.dashboard.get_summary(user=user).get('total_vendors', 0)
        except Exception:
            total_vendors = 0
        summary = {'total_vendors': total_vendors, 'inactive_vendors': len(vendors)}
        return self._payload(headers=headers, rows=rows, summary=summary)


class InventoryReportService(BaseReportService):
    """Inventory report — reuses BI InventoryService."""

    report_type = ReportType.INVENTORY

    def generate(self, *, user: User, **filters) -> dict:
        data = InventoryService().get_inventory(user=user, **filters)
        headers = ['Item ID', 'Display Name', 'Vendor', 'Cost', 'Type']
        rows = [
            [
                i.get('itemId'),
                i.get('displayName'),
                i.get('vendorName'),
                i.get('cost'),
                i.get('type'),
            ]
            for i in data.get('items', [])
        ]
        summary = {
            'total_items': data.get('total_items'),
            'inventory_value': data.get('inventory_value'),
            'low_stock_count': len(data.get('low_stock_items', [])),
            'currency': data.get('currency', 'USD'),
        }
        return self._payload(headers=headers, rows=rows, summary=summary)


class FinanceReportService(BaseReportService):
    """Finance report — reuses BI FinanceService."""

    report_type = ReportType.FINANCE

    def generate(self, *, user: User, **filters) -> dict:
        data = FinanceService().get_finance(user=user, **filters)
        headers = ['Metric', 'Value']
        metric_map = {
            'Total Receivables': data.get('receivables', {}).get('total_receivable'),
            'Overdue Amount': data.get('overdue', {}).get('total_overdue_amount'),
            'Overdue Count': data.get('overdue', {}).get('overdue_invoice_count'),
            'Payables': data.get('payables'),
            'Revenue': data.get('revenue'),
            'Profit': data.get('profit'),
        }
        rows = [[k, v] for k, v in metric_map.items()]
        summary = {'currency': data.get('currency', 'USD'), 'window': data.get('window')}
        return self._payload(headers=headers, rows=rows, summary=summary)


class InvoiceReportService(BaseReportService):
    """Invoice report — invoice pipeline KPIs from local models."""

    report_type = ReportType.INVOICE

    def generate(self, *, user: User, **filters) -> dict:
        window = self.resolve(**filters)
        company = self._company(user)
        batches = InvoiceBatch.objects.filter(company=company)
        if window:
            batches = batches.filter(created_at__lt=window['end_date'] + 'T23:59:59')

        headers = ['Batch ID', 'Total Files', 'Processed', 'Failed', 'Status', 'Created At']
        rows = [
            [str(b.id), b.total_files, b.processed_files, b.failed_files, b.status, b.created_at.isoformat()]
            for b in batches.order_by('-created_at')[:100]
        ]
        summary = {
            'batches': batches.count(),
            'files': sum(b.total_files for b in batches[:100]),
        }
        return self._payload(headers=headers, rows=rows, summary=summary)


class OCRReportService(BaseReportService):
    """OCR report — OCR usage & success from local models."""

    report_type = ReportType.OCR

    def generate(self, *, user: User, **filters) -> dict:
        window = self.resolve(**filters)
        company = self._company(user)
        qs = OCRUpload.objects.all()
        if company is not None:
            qs = qs.filter(user__company=company)
        if window:
            qs = qs.filter(created_at__lt=window['end_date'] + 'T23:59:59')

        headers = ['Filename', 'Status', 'Size (bytes)', 'Duration (ms)', 'Created At']
        rows = [
            [
                u.original_filename,
                u.status,
                u.file_size,
                u.processing_duration_ms,
                u.created_at.isoformat(),
            ]
            for u in qs[:100]
        ]
        total = qs.count()
        completed = qs.filter(status=OCRUpload.Status.COMPLETED).count()
        failed = qs.filter(status=OCRUpload.Status.FAILED).count()
        summary = {
            'total': total,
            'completed': completed,
            'failed': failed,
            'success_rate': round((completed / total) * 100, 2) if total else 0.0,
        }
        return self._payload(headers=headers, rows=rows, summary=summary)


class AIUsageReportService(BaseReportService):
    """AI usage report — AI audit log KPIs from local models."""

    report_type = ReportType.AI_USAGE

    def generate(self, *, user: User, **filters) -> dict:
        window = self.resolve(**filters)
        company = self._company(user)
        qs = AIAuditLog.objects.all()
        if company is not None:
            qs = qs.filter(user__company=company)
        if window:
            qs = qs.filter(created_at__lt=window['end_date'] + 'T23:59:59')

        headers = ['Provider', 'Model', 'Success', 'Latency (ms)', 'Created At']
        rows = [
            [a.provider, a.model, a.success, a.latency_ms, a.created_at.isoformat()]
            for a in qs[:100]
        ]
        total = qs.count()
        success = qs.filter(success=True).count()
        summary = {
            'total_calls': total,
            'success_calls': success,
            'success_rate': round((success / total) * 100, 2) if total else 0.0,
        }
        return self._payload(headers=headers, rows=rows, summary=summary)


class SyncReportService(BaseReportService):
    """NetSuite sync report — sync runs from local models."""

    report_type = ReportType.NETSUITE_SYNC

    def generate(self, *, user: User, **filters) -> dict:
        company = self._company(user)
        qs = SyncRun.objects.all()
        if company is not None:
            qs = qs.filter(connection__user__company=company)

        headers = ['Status', 'Trigger', 'Records', 'Failed', 'Started At']
        rows = [
            [r.status, r.trigger, r.records_processed, r.records_failed, r.started_at.isoformat() if r.started_at else '']
            for r in qs[:100]
        ]
        total = qs.count()
        success = qs.filter(status='success').count()
        failed = qs.filter(status='failed').count()
        summary = {
            'total_runs': total,
            'success_runs': success,
            'failed_runs': failed,
            'success_rate': round((success / total) * 100, 2) if total else 0.0,
        }
        return self._payload(headers=headers, rows=rows, summary=summary)


class ReportFactory:
    """Maps a report type string to its dedicated report service."""

    _registry = {
        ReportType.SALES: SalesReportService,
        ReportType.PURCHASE: PurchaseReportService,
        ReportType.CUSTOMER: CustomerReportService,
        ReportType.VENDOR: VendorReportService,
        ReportType.INVENTORY: InventoryReportService,
        ReportType.FINANCE: FinanceReportService,
        ReportType.INVOICE: InvoiceReportService,
        ReportType.OCR: OCRReportService,
        ReportType.AI_USAGE: AIUsageReportService,
        ReportType.NETSUITE_SYNC: SyncReportService,
    }

    @classmethod
    def get_service(cls, report_type: str) -> BaseReportService:
        service_class = cls._registry.get(report_type)
        if service_class is None:
            raise ValueError(f'Unsupported report type: {report_type}')
        return service_class()

    @classmethod
    def supported_types(cls) -> list[str]:
        return list(cls._registry.keys())


def generate_report_data(*, report_type: str, user: User, **filters) -> dict:
    """Facade used by views and Celery tasks."""
    service = ReportFactory.get_service(report_type)
    return service.generate(user=user, **filters)
