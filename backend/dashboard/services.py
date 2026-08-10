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


class DashboardAggregateService:
    """
    Aggregates cross-module dashboard data for the Executive Dashboard.

    Reuses existing services and models. No fake data. All counts come
    from real database records.
    """

    def __init__(self):
        self.netsuite_service = NetSuiteDataService()

    def get_executive_summary(self, *, user: User) -> dict:
        company = getattr(user, 'company', None)
        if not company:
            return self._empty_summary()

        from accounts.models import User as UserModel
        from invitations.models import Invitation, InvitationStatus
        from netsuite.models import NetSuiteConnection
        from invoice.models import InvoiceBatch, InvoiceFile, FileStatus
        from ai.models import AIConversation, AIMessage
        from reports_engine.models import ReportHistory
        from superadmin.models import CompanyPlan
        from analytics.services import AnalyticsService

        # Employee stats
        total_employees = UserModel.objects.filter(company=company).count()
        active_employees = UserModel.objects.filter(company=company, is_active=True).count()

        # Invitation stats
        pending_invitations = Invitation.objects.filter(
            company=company, status=InvitationStatus.PENDING
        ).count()

        # NetSuite connections
        connected_netsuite = NetSuiteConnection.objects.filter(
            company=company, is_active=True
        ).count()

        # Invoice stats
        invoice_files_qs = InvoiceFile.objects.filter(batch__company=company)
        invoices_uploaded = invoice_files_qs.count()
        invoices_pending_review = invoice_files_qs.filter(
            status__in=[FileStatus.EXTRACTED, FileStatus.REVIEW_REQUIRED]
        ).count()
        approved_invoices = invoice_files_qs.filter(
            status__in=[FileStatus.APPROVED, FileStatus.READY_FOR_NETSUITE]
        ).count()
        ocr_failed = invoice_files_qs.filter(status=FileStatus.FAILED).count()

        # Reports generated
        reports_generated = ReportHistory.objects.filter(company=company).count()

        # AI requests
        ai_requests = AIMessage.objects.filter(
            conversation__user__company=company
        ).count()

        # Subscription
        subscription = CompanyPlan.objects.filter(
            company=company,
            status__in=['ACTIVE', 'TRIAL'],
        ).select_related('plan').first()
        subscription_plan = subscription.plan.name if subscription else None
        plan_expiry = subscription.end_date.isoformat() if subscription and subscription.end_date else None

        # Storage used (approximate from media files)
        storage_used_mb = self._calculate_storage_used(company)

        # AI / OCR credits from the active plan
        ai_credits = subscription.plan.ai_credits if subscription else 0
        ocr_credits = subscription.plan.ocr_credits if subscription else 0

        # Modules enabled count
        from tenancy.models import CompanyModule
        modules_enabled = CompanyModule.objects.filter(company=company, enabled=True).count()

        return {
            'total_employees': total_employees,
            'active_employees': active_employees,
            'pending_invitations': pending_invitations,
            'connected_netsuite': connected_netsuite,
            'invoices_uploaded': invoices_uploaded,
            'invoices_pending_review': invoices_pending_review,
            'approved_invoices': approved_invoices,
            'ocr_failed': ocr_failed,
            'reports_generated': reports_generated,
            'ai_requests': ai_requests,
            'subscription_plan': subscription_plan,
            'plan_expiry': plan_expiry,
            'storage_used_mb': storage_used_mb,
            'ai_credits': ai_credits,
            'ocr_credits': ocr_credits,
            'modules_enabled': modules_enabled,
        }

    def get_invoice_charts(self, *, user: User) -> dict:
        company = getattr(user, 'company', None)
        if not company:
            return {'by_status': [], 'by_month': [], 'ocr_success_vs_failed': []}

        from invoice.models import InvoiceBatch, InvoiceFile, FileStatus
        from django.db.models import Count
        from django.utils import timezone
        import datetime

        # Invoices by status
        status_counts = (
            InvoiceFile.objects.filter(batch__company=company)
            .values('status')
            .annotate(count=Count('id'))
            .order_by('-count')
        )
        by_status = [
            {'status': item['status'], 'count': item['count']}
            for item in status_counts
        ]

        # Invoices by month (last 6 months)
        six_months_ago = timezone.now().date() - datetime.timedelta(days=180)
        monthly_counts = (
            InvoiceBatch.objects.filter(
                company=company,
                created_at__date__gte=six_months_ago,
            )
            .values('created_at__year', 'created_at__month')
            .annotate(count=Count('id'))
            .order_by('created_at__year', 'created_at__month')
        )
        by_month = [
            {
                'month': f"{item['created_at__year']}-{item['created_at__month']:02d}",
                'count': item['count'],
            }
            for item in monthly_counts
        ]

        # OCR success vs failed
        success_count = InvoiceFile.objects.filter(
            batch__company=company,
            status__in=[FileStatus.EXTRACTED, FileStatus.APPROVED, FileStatus.READY_FOR_NETSUITE],
        ).count()
        failed_count = InvoiceFile.objects.filter(
            batch__company=company, status=FileStatus.FAILED
        ).count()
        ocr_success_vs_failed = [
            {'status': 'Success', 'count': success_count},
            {'status': 'Failed', 'count': failed_count},
        ]

        return {
            'by_status': by_status,
            'by_month': by_month,
            'ocr_success_vs_failed': ocr_success_vs_failed,
        }

    def get_employee_growth(self, *, user: User) -> list:
        company = getattr(user, 'company', None)
        if not company:
            return []

        from accounts.models import User as UserModel
        from django.db.models import Count
        from django.utils import timezone
        import datetime

        twelve_months_ago = timezone.now().date() - datetime.timedelta(days=365)
        monthly_counts = (
            UserModel.objects.filter(company=company, created_at__date__gte=twelve_months_ago)
            .values('created_at__year', 'created_at__month')
            .annotate(count=Count('id'))
            .order_by('created_at__year', 'created_at__month')
        )
        return [
            {
                'month': f"{item['created_at__year']}-{item['created_at__month']:02d}",
                'count': item['count'],
            }
            for item in monthly_counts
        ]

    def get_ai_usage(self, *, user: User) -> list:
        company = getattr(user, 'company', None)
        if not company:
            return []

        from ai.models import AIMessage, AIConversation
        from django.db.models import Count
        from django.utils import timezone
        import datetime

        twelve_months_ago = timezone.now().date() - datetime.timedelta(days=365)
        monthly_counts = (
            AIMessage.objects.filter(conversation__user__company=company, created_at__date__gte=twelve_months_ago)
            .values('created_at__year', 'created_at__month')
            .annotate(count=Count('id'))
            .order_by('created_at__year', 'created_at__month')
        )
        return [
            {
                'month': f"{item['created_at__year']}-{item['created_at__month']:02d}",
                'count': item['count'],
            }
            for item in monthly_counts
        ]

    def get_activity_feed(self, *, user: User, limit: int = 10) -> dict:
        company = getattr(user, 'company', None)

        if not company:
            return {
                'recent_employees': [],
                'recent_invoices': [],
                'recent_ocr_jobs': [],
                'recent_reports': [],
                'recent_ai_conversations': [],
                'recent_netsuite_syncs': [],
            }

        from accounts.models import User as UserModel
        from invoice.models import InvoiceBatch, InvoiceFile
        from ai.models import AIConversation
        from reports_engine.models import ReportHistory
        from netsuite.models import NetSuiteConnection

        # ---------------------------------------------------------
        # Determine whether the current user is a Company Admin.
        # ---------------------------------------------------------

        user_roles_names = set(
            user.user_roles
            .select_related('role')
            .values_list('role__name', flat=True)
        )

        is_company_admin = 'Company Admin' in user_roles_names

        # ---------------------------------------------------------
        # Company Admin:
        #   Show company-wide activity.
        #
        # Employee:
        #   Show only activity created/uploaded by this user.
        # ---------------------------------------------------------

        if is_company_admin:
            recent_employees = list(
                UserModel.objects.filter(company=company)
                .order_by('-created_at')[:5]
                .values(
                    'id',
                    'email',
                    'first_name',
                    'last_name',
                    'created_at',
                )
            )

            recent_invoices = list(
                InvoiceFile.objects.filter(
                    batch__company=company
                )
                .order_by('-created_at')[:5]
                .values(
                    'id',
                    'original_filename',
                    'status',
                    'created_at',
                )
            )

            recent_ocr_jobs = list(
                InvoiceBatch.objects.filter(
                    company=company
                )
                .order_by('-created_at')[:5]
                .values(
                    'id',
                    'total_files',
                    'processed_files',
                    'failed_files',
                    'status',
                    'created_at',
                )
            )

            recent_reports = list(
                ReportHistory.objects.filter(
                    company=company
                )
                .order_by('-generated_at')[:5]
                .values(
                    'id',
                    'report_type',
                    'status',
                    'generated_at',
                )
            )

            recent_ai_conversations = list(
                AIConversation.objects.filter(
                    user__company=company
                )
                .order_by('-updated_at')[:5]
                .values(
                    'id',
                    'title',
                    'updated_at',
                )
            )

            recent_netsuite_syncs = list(
                NetSuiteConnection.objects.filter(
                    company=company
                )
                .order_by('-last_synced_at')[:5]
                .values(
                    'id',
                    'client_name',
                    'status',
                    'last_synced_at',
                )
            )

        else:
            # -----------------------------------------------------
            # Normal Employee:
            # Only show activity belonging to the logged-in user.
            # -----------------------------------------------------

            recent_employees = []

            recent_invoices = list(
                InvoiceFile.objects.filter(
                    batch__uploaded_by=user
                )
                .order_by('-created_at')[:5]
                .values(
                    'id',
                    'original_filename',
                    'status',
                    'created_at',
                )
            )

            recent_ocr_jobs = list(
                InvoiceBatch.objects.filter(
                    uploaded_by=user
                )
                .order_by('-created_at')[:5]
                .values(
                    'id',
                    'total_files',
                    'processed_files',
                    'failed_files',
                    'status',
                    'created_at',
                )
            )

            recent_reports = list(
                ReportHistory.objects.filter(
                    created_by=user
                )
                .order_by('-generated_at')[:5]
                .values(
                    'id',
                    'report_type',
                    'status',
                    'generated_at',
                )
            )

            recent_ai_conversations = list(
                AIConversation.objects.filter(
                    user=user
                )
                .order_by('-updated_at')[:5]
                .values(
                    'id',
                    'title',
                    'updated_at',
                )
            )

            recent_netsuite_syncs = list(
                NetSuiteConnection.objects.filter(
                    user=user
                )
                .order_by('-last_synced_at')[:5]
                .values(
                    'id',
                    'client_name',
                    'status',
                    'last_synced_at',
                )
            )

        return {
            'recent_employees': recent_employees,
            'recent_invoices': recent_invoices,
            'recent_ocr_jobs': recent_ocr_jobs,
            'recent_reports': recent_reports,
            'recent_ai_conversations': recent_ai_conversations,
            'recent_netsuite_syncs': recent_netsuite_syncs,
        }

    def _calculate_storage_used(self, company) -> float | None:
        """
        Approximate storage used by company files in MB.
        Returns None if unavailable.
        """
        try:
            from django.core.files.storage import default_storage
            from pathlib import Path

            total_bytes = 0
            for root, dirs, files in default_storage.walk(''):
                for f in files:
                    fp = Path(root) / f
                    if fp.exists():
                        total_bytes += fp.stat().st_size
            return round(total_bytes / (1024 * 1024), 2)
        except Exception:
            return None

    def _empty_summary(self) -> dict:
        return {
            'total_employees': 0,
            'active_employees': 0,
            'pending_invitations': 0,
            'connected_netsuite': 0,
            'invoices_uploaded': 0,
            'invoices_pending_review': 0,
            'approved_invoices': 0,
            'ocr_failed': 0,
            'reports_generated': 0,
            'ai_requests': 0,
            'subscription_plan': None,
            'plan_expiry': None,
            'storage_used_mb': None,
            'ai_credits': 0,
            'ocr_credits': 0,
            'modules_enabled': 0,
        }
