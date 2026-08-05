"""
BI business logic.

Each service is a thin orchestrator that reuses the existing
AnalyticsService, DashboardService, NetSuiteDataService or local models
(InvoiceBatch, InvoiceFile, OCRUpload, AIAuditLog, SyncRun,
NetSuiteConnection) — never duplicating business logic and never poking
NetSuite directly. Every method takes ``user`` and derives the company
from ``user.company`` (TenantMiddleware also sets ``request.company``).

All result payloads are returned chart-ready from the backend so the
frontend does no reshaping.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from django.db.models import Avg, Count, Q
from django.utils import timezone

from accounts.models import User
from ai.exceptions import AIProviderNotConfiguredException, AIProviderRequestException
from ai.providers import AIProviderFactory
from analytics.services import AnalyticsService
from dashboard.services import DashboardService
from invoice.models import FileStatus, InvoiceBatch
from netsuite.models import NetSuiteConnection
from ocr.models import OCRUpload
from sync.models import SyncRun

from bi.utils.date_ranges import resolve_date_range

logger = logging.getLogger(__name__)


class ServiceMixin:
    """Shared helpers for the BI services."""

    def __init__(self):
        self.analytics = AnalyticsService()
        self.dashboard = DashboardService()

    def resolve(self, **kwargs) -> dict:
        return resolve_date_range(**kwargs)

    @staticmethod
    def _pct(current: float, previous: float) -> float | None:
        """Percentage change vs previous period. None when previous is 0."""
        if previous == 0:
            return None
        return round(((current - previous) / previous) * 100, 2)

    def _company(self, user: User):
        return getattr(user, 'company', None)


class SummaryService(ServiceMixin):
    """Executive dashboard summary — the top-level KPI snapshot."""

    def get_summary(self, *, user: User, **filters) -> dict[str, Any]:
        window = self.resolve(**filters)
        company = self._company(user)

        # NetSuite-driven KPIs (reuse existing services).
        try:
            sales_summary = self.analytics.get_sales_summary(user=user)
        except Exception as exc:  # NetSuite may be disconnected
            logger.warning('BI summary sales failed: %s', exc)
            sales_summary = None

        try:
            receivables = self.analytics.get_total_receivables(user=user)
        except Exception as exc:
            logger.warning('BI summary receivables failed: %s', exc)
            receivables = None

        try:
            overdue = self.analytics.get_overdue_invoices_summary(user=user)
        except Exception as exc:
            logger.warning('BI summary overdue failed: %s', exc)
            overdue = None

        # Local invoice-processing pipeline KPIs.
        invoice_stats = self._invoice_pipeline_stats(company=company, window=window)

        # OCR success rate.
        ocr_stats = self._ocr_stats(company=company, window=window)

        # AI usage.
        ai_stats = self._ai_stats(company=company, window=window)

        # NetSuite sync status.
        sync_stats = self._sync_stats(company=company)

        return {
            'window': window,
            'revenue': {
                'sales_revenue': sales_summary.get('total_sales_revenue') if sales_summary else None,
                'invoice_revenue': sales_summary.get('total_invoice_revenue') if sales_summary else None,
                'total_sales_orders': sales_summary.get('total_sales_orders') if sales_summary else None,
                'total_invoices': sales_summary.get('total_invoices') if sales_summary else None,
                'average_order_value': sales_summary.get('average_order_value') if sales_summary else None,
                'currency': (sales_summary or {}).get('currency', 'USD'),
            },
            'receivables': receivables or {},
            'overdue': overdue or {},
            'invoice_pipeline': invoice_stats,
            'ocr': ocr_stats,
            'ai': ai_stats,
            'sync': sync_stats,
        }

    def _invoice_pipeline_stats(self, *, company, window) -> dict:
        if company is None:
            return {'batches': 0, 'files': 0, 'approved': 0, 'failed': 0, 'processing': 0}
        batches = InvoiceBatch.objects.filter(company=company)
        if window:
            batches = batches.filter(created_at__lt=window['end_date'] + 'T23:59:59')
        total_batches = batches.count()
        total_files = sum(b.total_files for b in batches)
        approved = sum(
            b.files.filter(status=FileStatus.APPROVED).count()
            for b in batches.prefetch_related('files')
        )
        failed = sum(
            b.files.filter(status=FileStatus.FAILED).count()
            for b in batches.prefetch_related('files')
        )
        processing = sum(
            b.files.filter(status__in=[FileStatus.UPLOADED, FileStatus.PROCESSING, FileStatus.EXTRACTED]).count()
            for b in batches.prefetch_related('files')
        )
        return {
            'batches': total_batches,
            'files': total_files,
            'approved': approved,
            'failed': failed,
            'processing': processing,
        }

    def _ocr_stats(self, *, company, window) -> dict:
        qs = OCRUpload.objects.all()
        if company is not None:
            qs = qs.filter(user__company=company)
        if window:
            qs = qs.filter(created_at__lt=window['end_date'] + 'T23:59:59')

        total = qs.count()
        completed = qs.filter(status=OCRUpload.Status.COMPLETED).count()
        failed = qs.filter(status=OCRUpload.Status.FAILED).count()
        success_rate = round((completed / total) * 100, 2) if total else 0.0
        avg_duration = qs.exclude(processing_duration_ms__isnull=True).aggregate(avg=Avg('processing_duration_ms')).get('avg')
        return {
            'total': total,
            'completed': completed,
            'failed': failed,
            'success_rate': success_rate,
            'avg_processing_ms': round(avg_duration, 2) if avg_duration else None,
        }

    def _ai_stats(self, *, company, window) -> dict:
        from ai.models import AIAuditLog
        qs = AIAuditLog.objects.all()
        if company is not None:
            qs = qs.filter(user__company=company)
        if window:
            qs = qs.filter(created_at__lt=window['end_date'] + 'T23:59:59')
        total_calls = qs.count()
        success_calls = qs.filter(success=True).count()
        success_rate = round((success_calls / total_calls) * 100, 2) if total_calls else 0.0
        avg_latency = qs.exclude(latency_ms__isnull=True).aggregate(avg=Avg('latency_ms')).get('avg')
        return {
            'total_calls': total_calls,
            'success_calls': success_calls,
            'success_rate': success_rate,
            'avg_latency_ms': round(avg_latency, 2) if avg_latency else None,
        }

    def _sync_stats(self, *, company) -> dict:
        qs = SyncRun.objects.all()
        if company is not None:
            qs = qs.filter(connection__user__company=company)
        total = qs.count()
        success = qs.filter(status='success').count()
        failed = qs.filter(status='failed').count()
        running = qs.filter(status='running').count()
        records_processed = qs.aggregate(total_records=Count('id')).get('total_records', 0)
        return {
            'total_runs': total,
            'success_runs': success,
            'failed_runs': failed,
            'running': running,
            'success_rate': round((success / total) * 100, 2) if total else 0.0,
        }


class SalesService(ServiceMixin):
    """Sales analytics — revenue, order volume, trends."""

    def get_sales(self, *, user: User, **filters) -> dict[str, Any]:
        window = self.resolve(**filters)

        # Current period revenue.
        current = self.analytics.get_revenue_for_period(
            user=user,
            start_date=window['start_date'],
            end_date=window['end_date'],
            transaction_type='SalesOrd',
        )
        # Previous equivalent window for trend comparison.
        prev_window = self._previous_window(window)
        previous = self.analytics.get_revenue_for_period(
            user=user,
            start_date=prev_window['start_date'],
            end_date=prev_window['end_date'],
            transaction_type='SalesOrd',
        )

        # Monthly trend for charts.
        trend = self.analytics.get_sales_trend_by_month(user=user, months=6)

        return {
            'window': window,
            'current': current,
            'previous': previous,
            'change_pct': self._pct(current.get('revenue', 0), previous.get('revenue', 0)),
            'trend': trend.get('trend', []),
            'currency': 'USD',
        }

    def _previous_window(self, window: dict) -> dict:
        from datetime import date, timedelta
        start = date.fromisoformat(window['start_date'])
        end = date.fromisoformat(window['end_date'])
        span = (end - start).days
        prev_end = start
        prev_start = start - timedelta(days=span)
        return {
            'start_date': prev_start.isoformat(),
            'end_date': prev_end.isoformat(),
        }


class PurchaseService(ServiceMixin):
    """Purchase analytics — purchase orders, vendor spend."""

    def get_purchase(self, *, user: User, **filters) -> dict[str, Any]:
        # Reuse NetSuiteDataService list methods for purchase orders.
        try:
            po_response = self.dashboard.netsuite_data_service.list_purchase_orders(user=user, limit=100, offset=0)
            items = po_response.get('items', [])
            total_results = po_response.get('totalResults', len(items))
        except Exception as exc:
            logger.warning('BI purchase failed: %s', exc)
            items, total_results = [], 0

        total_spend = sum(float(i.get('total') or 0) for i in items)
        avg_order = round(total_spend / len(items), 2) if items else 0.0

        return {
            'window': self.resolve(**filters),
            'total_purchase_orders': total_results,
            'total_spend': round(total_spend, 2),
            'average_order_value': avg_order,
            'currency': 'USD',
            'recent_orders': items[:20],
        }


class CustomerService(ServiceMixin):
    """Customer analytics — top customers, revenue by customer, churn risk."""

    def get_customers(self, *, user: User, **filters) -> dict[str, Any]:
        window = self.resolve(**filters)

        try:
            top_customers = self.analytics.get_top_customers(user=user, limit=10)
        except Exception as exc:
            logger.warning('BI customer top failed: %s', exc)
            top_customers = []

        try:
            revenue_by_customer = self.analytics.get_revenue_by_customer(user=user, limit=10, transaction_type='SalesOrd')
        except Exception as exc:
            logger.warning('BI customer revenue failed: %s', exc)
            revenue_by_customer = []

        try:
            churn_risk = self.analytics.get_customer_churn_risk(user=user, limit=10)
        except Exception as exc:
            logger.warning('BI customer churn failed: %s', exc)
            churn_risk = []

        try:
            total_receivables = self.analytics.get_total_receivables(user=user)
        except Exception as exc:
            logger.warning('BI customer receivables failed: %s', exc)
            total_receivables = {}

        return {
            'window': window,
            'top_customers': top_customers,
            'revenue_by_customer': revenue_by_customer,
            'churn_risk': churn_risk,
            'total_receivables': total_receivables,
            'currency': 'USD',
        }


class InventoryService(ServiceMixin):
    """Inventory analytics — item counts, low-stock, inventory value."""

    def get_inventory(self, *, user: User, **filters) -> dict[str, Any]:
        window = self.resolve(**filters)

        try:
            inventory_response = self.dashboard.netsuite_data_service.list_inventory_items(user=user, limit=100, offset=0)
            items = inventory_response.get('items', [])
            total_items = inventory_response.get('totalResults', len(items))
        except Exception as exc:
            logger.warning('BI inventory failed: %s', exc)
            items, total_items = [], 0

        # Inventory value using cost field where available.
        total_value = sum(float(i.get('cost') or 0) for i in items)
        low_stock = [i for i in items if i.get('cost') is not None]  # placeholder for low-stock logic

        try:
            low_stock = self.analytics.get_low_inventory(user=user, limit=50)
        except Exception as exc:
            logger.warning('BI inventory low stock failed: %s', exc)
            low_stock = []

        return {
            'window': window,
            'total_items': total_items,
            'inventory_value': round(total_value, 2),
            'low_stock_items': low_stock,
            'currency': 'USD',
            'items': items,
        }


class FinanceService(ServiceMixin):
    """Finance analytics — receivables, payables, profit, expense."""

    def get_finance(self, *, user: User, **filters) -> dict[str, Any]:
        window = self.resolve(**filters)

        try:
            receivables = self.analytics.get_total_receivables(user=user)
        except Exception as exc:
            logger.warning('BI finance receivables failed: %s', exc)
            receivables = {}

        try:
            overdue = self.analytics.get_overdue_invoices_summary(user=user)
        except Exception as exc:
            logger.warning('BI finance overdue failed: %s', exc)
            overdue = {}

        try:
            sales_summary = self.analytics.get_sales_summary(user=user)
            revenue = sales_summary.get('total_invoice_revenue', 0)
        except Exception as exc:
            logger.warning('BI finance revenue failed: %s', exc)
            revenue = 0

        # Payables: derive from purchase orders (approximation from available data).
        try:
            po_response = self.dashboard.netsuite_data_service.list_purchase_orders(user=user, limit=100, offset=0)
            payables = sum(float(i.get('total') or 0) for i in po_response.get('items', []))
        except Exception as exc:
            logger.warning('BI finance payables failed: %s', exc)
            payables = 0

        # Profit: revenue minus payables (best-effort proxy when expense data is unavailable).
        profit = round(revenue - payables, 2)

        return {
            'window': window,
            'receivables': receivables,
            'overdue': overdue,
            'payables': round(payables, 2),
            'revenue': round(revenue, 2),
            'profit': profit,
            'currency': 'USD',
        }


class AlertService(ServiceMixin):
    """
    Executive alerts with severity levels.

    Deterministic, rule-based alerts derived from real computed KPIs —
    no fabricated data.
    """

    SEVERITY_CRITICAL = 'critical'
    SEVERITY_WARNING = 'warning'
    SEVERITY_INFO = 'info'

    def get_alerts(self, *, user: User, **filters) -> dict[str, Any]:
        window = self.resolve(**filters)
        alerts = []

        # Overdue receivables alert.
        try:
            overdue = self.analytics.get_overdue_invoices_summary(user=user)
            if overdue.get('overdue_invoice_count', 0) > 0:
                alerts.append(self._alert(
                    severity=self.SEVERITY_WARNING,
                    title='Overdue receivables',
                    message=f"{overdue.get('overdue_invoice_count', 0)} invoices totaling "
                            f"${overdue.get('total_overdue_amount', 0):,.2f} are overdue.",
                    metric='overdue_receivables',
                    value=overdue.get('total_overdue_amount', 0),
                    currency=overdue.get('currency', 'USD'),
                ))
        except Exception as exc:
            logger.warning('BI alert overdue skipped: %s', exc)

        # Sync health alert.
        try:
            sync = self._sync_stats(company=self._company(user))
            if sync.get('failed_runs', 0) > 0:
                alerts.append(self._alert(
                    severity=self.SEVERITY_CRITICAL,
                    title='NetSuite sync failures',
                    message=f"{sync.get('failed_runs', 0)} of {sync.get('total_runs', 0)} sync runs failed.",
                    metric='sync_failures',
                    value=sync.get('failed_runs', 0),
                ))
        except Exception as exc:
            logger.warning('BI alert sync skipped: %s', exc)

        # Invoice pipeline failures alert.
        try:
            invoice_stats = self._invoice_pipeline_stats(company=self._company(user), window=window)
            if invoice_stats.get('failed', 0) > 0:
                alerts.append(self._alert(
                    severity=self.SEVERITY_WARNING,
                    title='Invoice processing failures',
                    message=f"{invoice_stats.get('failed', 0)} invoices failed processing.",
                    metric='invoice_failures',
                    value=invoice_stats.get('failed', 0),
                ))
        except Exception as exc:
            logger.warning('BI alert invoice skipped: %s', exc)

        # OCR success rate alert.
        try:
            ocr = self._ocr_stats(company=self._company(user), window=window)
            if ocr.get('total', 0) > 0 and ocr.get('success_rate', 100) < 80:
                alerts.append(self._alert(
                    severity=self.SEVERITY_WARNING,
                    title='OCR success rate below threshold',
                    message=f"OCR success rate is {ocr.get('success_rate')}%.",
                    metric='ocr_success_rate',
                    value=ocr.get('success_rate'),
                    unit='%',
                ))
        except Exception as exc:
            logger.warning('BI alert ocr skipped: %s', exc)

        # NetSuite connection health alert.
        try:
            connection = self._active_connection(company=self._company(user))
            if connection and connection.consecutive_failures >= 3:
                alerts.append(self._alert(
                    severity=self.SEVERITY_CRITICAL,
                    title='NetSuite connection unhealthy',
                    message=f"Connection '{connection.client_name or connection.netsuite_account_id}' "
                            f"has {connection.consecutive_failures} consecutive failures.",
                    metric='netsuite_connection_health',
                    value=connection.consecutive_failures,
                ))
        except Exception as exc:
            logger.warning('BI alert connection skipped: %s', exc)

        # No alerts — return a single info card.
        if not alerts:
            alerts.append(self._alert(
                severity=self.SEVERITY_INFO,
                title='All systems nominal',
                message='No critical alerts in the selected period.',
                metric='no_alerts',
                value=0,
            ))

        return {
            'window': window,
            'alerts': alerts,
        }

    @staticmethod
    def _alert(*, severity: str, title: str, message: str, metric: str, value: Any, currency: str | None = None, unit: str | None = None) -> dict:
        return {
            'severity': severity,
            'title': title,
            'message': message,
            'metric': metric,
            'value': value,
            'currency': currency,
            'unit': unit,
        }

    # Reuse helpers from SummaryService-style logic (kept local to avoid coupling).
    def _sync_stats(self, *, company) -> dict:
        qs = SyncRun.objects.all()
        if company is not None:
            qs = qs.filter(connection__user__company=company)
        total = qs.count()
        success = qs.filter(status='success').count()
        failed = qs.filter(status='failed').count()
        return {
            'total_runs': total,
            'success_runs': success,
            'failed_runs': failed,
            'success_rate': round((success / total) * 100, 2) if total else 0.0,
        }

    def _invoice_pipeline_stats(self, *, company, window) -> dict:
        if company is None:
            return {'batches': 0, 'files': 0, 'approved': 0, 'failed': 0, 'processing': 0}
        batches = InvoiceBatch.objects.filter(company=company)
        if window:
            batches = batches.filter(created_at__lt=window['end_date'] + 'T23:59:59')
        failed = sum(
            b.files.filter(status=FileStatus.FAILED).count()
            for b in batches.prefetch_related('files')
        )
        return {'failed': failed}

    def _ocr_stats(self, *, company, window) -> dict:
        qs = OCRUpload.objects.all()
        if company is not None:
            qs = qs.filter(user__company=company)
        if window:
            qs = qs.filter(created_at__lt=window['end_date'] + 'T23:59:59')
        total = qs.count()
        completed = qs.filter(status=OCRUpload.Status.COMPLETED).count()
        return {
            'total': total,
            'success_rate': round((completed / total) * 100, 2) if total else 0.0,
        }

    def _active_connection(self, *, company):
        if company is None:
            return None
        return NetSuiteConnection.objects.filter(
            user__company=company, is_active=True,
        ).order_by('-updated_at').first()


class InsightService(ServiceMixin):
    """
    AI-generated executive insights.

    Only summarized, deterministic KPIs are passed to the AI provider —
    never raw NetSuite data. If the provider is not configured or fails,
    the service returns a graceful fallback rather than crashing the page.
    """

    def get_insights(self, *, user: User, **filters) -> dict[str, Any]:
        window = self.resolve(**filters)

        # Build a compact, summarized KPI payload.
        summary_service = SummaryService()
        summary = summary_service.get_summary(user=user, **filters)

        sales_service = SalesService()
        sales = sales_service.get_sales(user=user, **filters)

        finance_service = FinanceService()
        finance = finance_service.get_finance(user=user, **filters)

        kpi_snapshot = {
            'window': window.get('label'),
            'sales_revenue': summary['revenue'].get('sales_revenue'),
            'invoice_revenue': summary['revenue'].get('invoice_revenue'),
            'total_receivables': summary['receivables'].get('total_receivable'),
            'overdue_amount': summary['overdue'].get('total_overdue_amount'),
            'overdue_count': summary['overdue'].get('overdue_invoice_count'),
            'sales_trend_change_pct': sales.get('change_pct'),
            'profit': finance.get('profit'),
            'payables': finance.get('payables'),
            'ocr_success_rate': summary['ocr'].get('success_rate'),
            'ai_success_rate': summary['ai'].get('success_rate'),
            'sync_success_rate': summary['sync'].get('success_rate'),
            'invoice_files_processed': summary['invoice_pipeline'].get('files'),
            'invoice_approval_rate': self._approval_rate(summary['invoice_pipeline']),
        }

        insight = self._generate(kpi_snapshot=kpi_snapshot)

        return {
            'window': window,
            'kpi_snapshot': kpi_snapshot,
            'insight': insight,
        }

    @staticmethod
    def _approval_rate(pipeline: dict) -> float | None:
        files = pipeline.get('files', 0)
        approved = pipeline.get('approved', 0)
        if not files:
            return None
        return round((approved / files) * 100, 2)

    def _generate(self, *, kpi_snapshot: dict) -> dict:
        try:
            provider = AIProviderFactory.create()
        except AIProviderNotConfiguredException as exc:
            logger.warning('BI insights provider not configured: %s', exc)
            return self._fallback(kpi_snapshot, reason='AI provider not configured')

        system_prompt = (
            'You are a CFO-grade executive analytics assistant. Given a summarized '
            'set of business KPIs, produce a concise executive insight. Respond only '
            'with valid JSON in exactly this shape: '
            '{"summary":"...","recommendation":"...","priority":"high|medium|low",'
            '"confidence":0.0-1.0}. Be specific and data-driven. Do not invent numbers.'
        )
        user_prompt = f"KPIs: {kpi_snapshot}"

        try:
            raw = provider.generate_response(system_prompt=system_prompt, user_prompt=user_prompt)
        except (AIProviderRequestException, AIProviderNotConfiguredException) as exc:
            logger.warning('BI insights generation failed: %s', exc)
            return self._fallback(kpi_snapshot, reason='AI provider unavailable')

        return self._parse(raw, kpi_snapshot)

    def _parse(self, raw: str, kpi_snapshot: dict) -> dict:
        import json
        data = {}
        try:
            # Strip markdown code fences if present.
            cleaned = raw.strip()
            if cleaned.startswith('```'):
                cleaned = cleaned.split('```', 2)[1]
                if cleaned.startswith('json'):
                    cleaned = cleaned[4:].strip()
            data = json.loads(cleaned)
        except (ValueError, IndexError):
            logger.warning('BI insights provider returned non-JSON; using fallback.')
            return self._fallback(kpi_snapshot, reason='Provider returned invalid format')

        return {
            'summary': data.get('summary', ''),
            'recommendation': data.get('recommendation', ''),
            'priority': data.get('priority', 'medium'),
            'confidence': data.get('confidence', 0.0),
            'generated_at': timezone.now().isoformat(),
        }

    def _fallback(self, kpi_snapshot: dict, *, reason: str) -> dict:
        """Deterministic fallback — no fake AI, but still useful and honest."""
        return {
            'summary': (
                f"Revenue for {kpi_snapshot.get('window')} was "
                f"${kpi_snapshot.get('invoice_revenue') or 0:,.2f}; "
                f"total receivables ${kpi_snapshot.get('total_receivables') or 0:,.2f}. "
                f"({reason})"
            ),
            'recommendation': 'Review the detailed finance and sales analytics for actions.',
            'priority': 'medium',
            'confidence': 0.0,
            'generated_at': timezone.now().isoformat(),
        }


class HealthService(ServiceMixin):
    """Executive system health — connectivity and pipeline status."""

    def get_health(self, *, user: User) -> dict[str, Any]:
        company = self._company(user)

        # NetSuite connection health.
        connection = self._active_connection(company=company)
        connection_health = 'disconnected'
        if connection:
            connection_health = connection.health

        # Invoice pipeline.
        invoice_stats = self._pipeline_health(company=company)

        # OCR.
        ocr = self._ocr_health(company=company)

        # AI.
        ai = self._ai_health(company=company)

        # Sync.
        sync = self._sync_health(company=company)

        return {
            'netsuite': {
                'connected': connection is not None,
                'health': connection_health,
                'last_synced_at': connection.last_synced_at.isoformat() if connection and connection.last_synced_at else None,
                'consecutive_failures': connection.consecutive_failures if connection else 0,
            },
            'invoice_pipeline': invoice_stats,
            'ocr': ocr,
            'ai': ai,
            'sync': sync,
        }

    def _active_connection(self, *, company):
        if company is None:
            return None
        return NetSuiteConnection.objects.filter(
            user__company=company, is_active=True,
        ).order_by('-updated_at').first()

    def _pipeline_health(self, *, company) -> dict:
        if company is None:
            return {'status': 'unknown', 'recent_failures': 0}
        qs = InvoiceBatch.objects.filter(company=company).order_by('-created_at')[:10]
        recent_failures = 0
        for b in qs:
            recent_failures += b.files.filter(status=FileStatus.FAILED).count()
        status = 'healthy' if recent_failures == 0 else 'degraded'
        return {'status': status, 'recent_failures': recent_failures}

    def _ocr_health(self, *, company) -> dict:
        qs = OCRUpload.objects.all()
        if company is not None:
            qs = qs.filter(user__company=company)
        recent = qs.order_by('-created_at')[:10]
        total = recent.count()
        failed = sum(1 for r in recent if r.status == OCRUpload.Status.FAILED)
        status = 'healthy' if failed == 0 else 'degraded'
        return {'status': status, 'recent_failures': failed, 'recent_total': total}

    def _ai_health(self, *, company) -> dict:
        from ai.models import AIAuditLog
        qs = AIAuditLog.objects.all()
        if company is not None:
            qs = qs.filter(user__company=company)
        recent = qs.order_by('-created_at')[:20]
        total = recent.count()
        failed = sum(1 for r in recent if not r.success)
        status = 'healthy' if failed == 0 else 'degraded'
        return {'status': status, 'recent_failures': failed, 'recent_total': total}

    def _sync_health(self, *, company) -> dict:
        qs = SyncRun.objects.all()
        if company is not None:
            qs = qs.filter(connection__user__company=company)
        recent = qs.order_by('-created_at')[:10]
        total = recent.count()
        failed = sum(1 for r in recent if r.status == 'failed')
        status = 'healthy' if failed == 0 else 'degraded'
        return {'status': status, 'recent_failures': failed, 'recent_total': total}
