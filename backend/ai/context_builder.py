"""
Builds the business context passed to the AI provider.

Per AI_CONTEXT.md ("Facts come from analytics. Explanations come from
AI."), this module never fabricates business data and never fetches raw
NetSuite data itself — it only orchestrates existing services
(DashboardService, BusinessInsightsService, InvoiceService) and assembles
their results. All actual NetSuite calls and business-metric logic live
in those services; this module owns none of it.

`netsuite_connected` reflects a real, current check against the user's
actual NetSuiteConnection (reusing netsuite's own repository rather than
querying the model directly here, per DRY). `business_context` is
populated when connected, combining:

- Dashboard context (summary, recent_customers, recent_sales_orders,
  recent_invoices) — pre-existing keys, unchanged.
- Business Insights (sales_summary, top_customers, overdue_invoices,
  inactive_vendors, low_inventory) — reused from BusinessInsightsService,
  not duplicated here.
- Local invoice/OCR context (invoice_stats, pending_invoices,
  approved_invoices, ocr_failures, recent_invoice_batches) — always
  available from the local database, independent of NetSuite.

Each insight is fetched independently and can fail without failing the
whole request: a failure is logged and that key is set to None (never
fabricated) while every other insight still gets built. An AI request
never crashes just because one specific query is slow or errors — the
assistant still answers using whatever context did come back.
"""

import logging

from django.utils import timezone
from django.core.cache import cache

from accounts.models import User
from analytics.services import AnalyticsService
from ai.business_context import AIRequestContext, BusinessContext
from dashboard.services import DashboardService
from invoice.models import InvoiceFile, InvoiceBatch, FileStatus
from netsuite.repositories import NetSuiteConnectionRepository

logger = logging.getLogger(__name__)

# Short TTL cache of the assembled context (not the LLM's answer — see
# ai/services.py's docstring for why: caching the final answer text
# would be actively wrong across different questions/conversations,
# but the *inputs* to the AI are safe and valuable to cache, since
# build_context() runs ~15 live SuiteQL calls that return the same
# result for rapid-fire follow-up questions within one chat session).
CONTEXT_CACHE_TTL_SECONDS = 60
CONTEXT_CACHE_KEY_PREFIX = 'ai_business_context'


def _current_month_range() -> tuple[str, str]:
    """First-of-this-month through first-of-next-month, as 'YYYY-MM-DD' strings."""
    today = timezone.now().date()
    start = today.replace(day=1)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    return start.isoformat(), end.isoformat()


def _previous_month_range() -> tuple[str, str]:
    """First-of-last-month through first-of-this-month, as 'YYYY-MM-DD' strings."""
    this_month_start, _ = _current_month_range()
    end = this_month_start
    today = timezone.now().date()
    if today.month == 1:
        start = today.replace(year=today.year - 1, month=12, day=1).isoformat()
    else:
        start = today.replace(month=today.month - 1, day=1).isoformat()
    return start, end


def _current_fiscal_year_range() -> tuple[str, str]:
    """
    Current fiscal year as 'YYYY-MM-DD' strings, assuming an April-to-March
    fiscal year (the common convention in India). If your NetSuite account
    is configured with a different fiscal year (e.g. calendar year, or a
    custom start month), adjust this function — it's a plain date
    calculation, not something derived from NetSuite itself.
    """
    today = timezone.now().date()
    if today.month >= 4:
        start = today.replace(month=4, day=1)
        end = start.replace(year=start.year + 1)
    else:
        end = today.replace(month=4, day=1)
        start = end.replace(year=end.year - 1)
    return start.isoformat(), end.isoformat()


def _safe_call(label: str, func):
    """
    Run one context-building call in isolation. On failure, log and
    return None instead of letting the exception propagate — this is
    what makes graceful degradation possible without repeating the same
    try/except block nine times in build_context(). Catches Exception
    broadly and deliberately: any failure mode from an external call
    (network error, unexpected NetSuite response shape, etc.) should
    degrade this one section, not crash the whole AI request — the same
    reasoning netsuite/client.py and ai/providers.py already apply around
    their own external calls.
    """
    try:
        return func()
    except Exception:
        logger.exception('Failed to build AI context section "%s"; omitting it.', label)
        return None


def _build_invoice_stats(user: User) -> dict | None:
    """Aggregate invoice counts and status breakdown for the user's company."""
    company = getattr(user, 'company', None)
    if not company:
        return None

    batches = InvoiceBatch.objects.filter(company=company)
    total_batches = batches.count()
    total_files = InvoiceFile.objects.filter(batch__company=company).count()

    status_counts = {}
    for status in FileStatus.values:
        status_counts[status] = InvoiceFile.objects.filter(
            batch__company=company, status=status
        ).count()

    failed = InvoiceFile.objects.filter(
        batch__company=company, status=FileStatus.FAILED
    ).count()

    return {
        'total_batches': total_batches,
        'total_files': total_files,
        'status_counts': status_counts,
        'failed_files': failed,
    }


def _build_pending_invoices(user: User, limit: int = 10) -> list | None:
    """Invoices pending review (EXTRACTED or REVIEW_REQUIRED)."""
    company = getattr(user, 'company', None)
    if not company:
        return None

    qs = InvoiceFile.objects.filter(
        batch__company=company,
        status__in=[FileStatus.EXTRACTED, FileStatus.REVIEW_REQUIRED],
    ).select_related('batch', 'extraction').order_by('-created_at')[:limit]

    return [
        {
            'file_id': str(f.id),
            'filename': f.original_filename,
            'status': f.status,
            'confidence': getattr(getattr(f, 'extraction', None), 'confidence_score', None),
            'batch_id': str(f.batch_id),
            'created_at': f.created_at.isoformat(),
        }
        for f in qs
    ]


def _build_approved_invoices(user: User, limit: int = 10) -> list | None:
    """Approved invoices ready for NetSuite."""
    company = getattr(user, 'company', None)
    if not company:
        return None

    qs = InvoiceFile.objects.filter(
        batch__company=company,
        status=FileStatus.APPROVED,
    ).select_related('batch', 'extraction').order_by('-created_at')[:limit]

    return [
        {
            'file_id': str(f.id),
            'filename': f.original_filename,
            'confidence': getattr(getattr(f, 'extraction', None), 'confidence_score', None),
            'batch_id': str(f.batch_id),
            'created_at': f.created_at.isoformat(),
        }
        for f in qs
    ]


def _build_ocr_failures(user: User, limit: int = 10) -> list | None:
    """Failed OCR/invoice files."""
    company = getattr(user, 'company', None)
    if not company:
        return None

    qs = InvoiceFile.objects.filter(
        batch__company=company,
        status=FileStatus.FAILED,
    ).select_related('batch').order_by('-created_at')[:limit]

    return [
        {
            'file_id': str(f.id),
            'filename': f.original_filename,
            'batch_id': str(f.batch_id),
            'created_at': f.created_at.isoformat(),
        }
        for f in qs
    ]


def _build_recent_invoice_batches(user: User, limit: int = 5) -> list | None:
    """Recent invoice batches for the user's company."""
    company = getattr(user, 'company', None)
    if not company:
        return None

    qs = InvoiceBatch.objects.filter(company=company).order_by('-created_at')[:limit]

    return [
        {
            'batch_id': str(b.id),
            'total_files': b.total_files,
            'processed_files': b.processed_files,
            'failed_files': b.failed_files,
            'status': b.status,
            'created_at': b.created_at.isoformat(),
        }
        for b in qs
    ]


def build_context(user: User) -> AIRequestContext:
    cache_key = f"{CONTEXT_CACHE_KEY_PREFIX}:{user.id}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    context = _build_context_uncached(user)
    cache.set(cache_key, context, CONTEXT_CACHE_TTL_SECONDS)
    return context


def _build_context_uncached(user: User) -> AIRequestContext:
    connection_repository = NetSuiteConnectionRepository()
    connection = connection_repository.get_by_user(user)
    netsuite_connected = bool(connection and connection.is_active)

    # Local invoice/OCR context — always available, independent of NetSuite.
    invoice_stats = _safe_call('invoice_stats', lambda: _build_invoice_stats(user))
    pending_invoices = _safe_call('pending_invoices', lambda: _build_pending_invoices(user))
    approved_invoices = _safe_call('approved_invoices', lambda: _build_approved_invoices(user))
    ocr_failures = _safe_call('ocr_failures', lambda: _build_ocr_failures(user))
    recent_invoice_batches = _safe_call(
        'recent_invoice_batches', lambda: _build_recent_invoice_batches(user)
    )

    if not netsuite_connected:
        return AIRequestContext(
            netsuite_connected=False,
            business_context=BusinessContext(
                invoice_stats=invoice_stats,
                pending_invoices=pending_invoices,
                approved_invoices=approved_invoices,
                ocr_failures=ocr_failures,
                recent_invoice_batches=recent_invoice_batches,
            ),
        )

    dashboard_service = DashboardService()
    analytics_service = AnalyticsService()

    business_context = {
        # Dashboard context — pre-existing keys, unchanged.
        'summary': _safe_call(
            'summary', lambda: dashboard_service.get_summary(user=user)
        ),
        'recent_customers': _safe_call(
            'recent_customers', lambda: dashboard_service.get_recent_customers(user=user)
        ),
        'recent_invoices': _safe_call(
            'recent_invoices', lambda: dashboard_service.get_recent_invoices(user=user)
        ),
        'recent_sales_orders': _safe_call(
            'recent_sales_orders',
            lambda: dashboard_service.get_recent_sales_orders(user=user),
        ),
        'recent_employees': _safe_call(
            'recent_employees', lambda: dashboard_service.get_recent_employees(user=user)
        ),
        # Business Insights — new, additive keys.
        'sales_summary': _safe_call(
            'sales_summary', lambda: analytics_service.get_sales_summary(user=user)
        ),
        'top_customers': _safe_call(
            'top_customers', lambda: analytics_service.get_top_customers(user=user)
        ),
        'overdue_invoices': _safe_call(
            'overdue_invoices',
            lambda: analytics_service.get_overdue_invoices(user=user),
        ),
        'overdue_invoices_summary': _safe_call(
            'overdue_invoices_summary',
            lambda: analytics_service.get_overdue_invoices_summary(user=user),
        ),
        'inactive_vendors': _safe_call(
            'inactive_vendors',
            lambda: analytics_service.get_inactive_vendors(user=user),
        ),
        'low_inventory': _safe_call(
            'low_inventory', lambda: analytics_service.get_low_inventory(user=user)
        ),
        'total_receivables': _safe_call(
            'total_receivables',
            lambda: analytics_service.get_total_receivables(user=user),
        ),
        'sales_trend': _safe_call(
            'sales_trend',
            lambda: analytics_service.get_sales_trend_by_month(user=user, months=6),
        ),
        'product_margins': _safe_call(
            'product_margins',
            lambda: analytics_service.get_product_margins(user=user),
        ),
        'customer_churn_risk': _safe_call(
            'customer_churn_risk',
            lambda: analytics_service.get_customer_churn_risk(user=user),
        ),
        # Revenue — new, additive keys.
        'top_customers_by_revenue': _safe_call(
            'top_customers_by_revenue',
            lambda: analytics_service.get_revenue_by_customer(user=user),
        ),
        'revenue_this_month': _safe_call(
            'revenue_this_month',
            lambda: analytics_service.get_revenue_for_period(
                user=user,
                start_date=_current_month_range()[0],
                end_date=_current_month_range()[1],
            ),
        ),
        'revenue_last_month': _safe_call(
            'revenue_last_month',
            lambda: analytics_service.get_revenue_for_period(
                user=user,
                start_date=_previous_month_range()[0],
                end_date=_previous_month_range()[1],
            ),
        ),
        'revenue_this_fiscal_year': _safe_call(
            'revenue_this_fiscal_year',
            lambda: analytics_service.get_revenue_for_period(
                user=user,
                start_date=_current_fiscal_year_range()[0],
                end_date=_current_fiscal_year_range()[1],
            ),
        ),
        # Local invoice/OCR context — additive, independent of NetSuite.
        'invoice_stats': invoice_stats,
        'pending_invoices': pending_invoices,
        'approved_invoices': approved_invoices,
        'ocr_failures': ocr_failures,
        'recent_invoice_batches': recent_invoice_batches,
    }

    return AIRequestContext(netsuite_connected=True, business_context=BusinessContext(**business_context))
