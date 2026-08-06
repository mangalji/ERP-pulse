"""
Invoice-domain tools.

Each tool wraps exactly one local invoice/OCR data query. No business logic
exists here — tools only delegate to the existing models/services.
"""

from typing import Any

from accounts.models import User
from ai.tools.base import SelfDescribingTool
from invoice.models import InvoiceFile, InvoiceBatch, FileStatus


class InvoiceStatsTool(SelfDescribingTool):
    """Aggregate invoice counts and status breakdown."""

    name = "get_invoice_stats"
    description = (
        "Returns aggregate invoice statistics: total batches, total files, "
        "counts by status (uploaded, processing, extracted, approved, rejected, "
        "failed, etc.), and failed file count. Use this to answer 'how many "
        "invoices do I have?' or 'invoice summary' or 'pending invoices count.'"
    )

    @property
    def parameters(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}}

    def execute(self, *, user: User, **kwargs) -> Any:
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


class PendingInvoicesTool(SelfDescribingTool):
    """Invoices pending review or extraction."""

    name = "get_pending_invoices"
    description = (
        "Returns invoices that are pending review or extraction "
        "(status: EXTRACTED or REVIEW_REQUIRED). Use this to answer "
        "'which invoices need review?' or 'pending invoices.'"
    )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Number of invoices to return.",
                    "default": 10,
                },
            },
        }

    def execute(self, *, user: User, limit: int = 10, **kwargs) -> Any:
        company = getattr(user, 'company', None)
        if not company:
            return []

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


class ApprovedInvoicesTool(SelfDescribingTool):
    """Approved invoices ready for NetSuite."""

    name = "get_approved_invoices"
    description = (
        "Returns invoices that have been approved and are ready for NetSuite "
        "(status: APPROVED or READY_FOR_NETSUITE). Use this to answer "
        "'which invoices are ready for NetSuite?' or 'approved invoices.'"
    )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Number of invoices to return.",
                    "default": 10,
                },
            },
        }

    def execute(self, *, user: User, limit: int = 10, **kwargs) -> Any:
        company = getattr(user, 'company', None)
        if not company:
            return []

        qs = InvoiceFile.objects.filter(
            batch__company=company,
            status__in=[FileStatus.APPROVED, FileStatus.READY_FOR_NETSUITE],
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


class OCRFailuresTool(SelfDescribingTool):
    """Failed OCR/invoice files."""

    name = "get_ocr_failures"
    description = (
        "Returns invoice files that failed OCR processing or extraction "
        "(status: FAILED). Use this to answer 'which invoices failed OCR?' "
        "or 'OCR failures' or 'failed invoices.'"
    )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Number of failures to return.",
                    "default": 10,
                },
            },
        }

    def execute(self, *, user: User, limit: int = 10, **kwargs) -> Any:
        company = getattr(user, 'company', None)
        if not company:
            return []

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


class RecentInvoiceBatchesTool(SelfDescribingTool):
    """Recent invoice batches."""

    name = "get_recent_invoice_batches"
    description = (
        "Returns recent invoice batches for the company. Use this to answer "
        "'show recent invoice batches' or 'latest batches.'"
    )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Number of batches to return.",
                    "default": 5,
                },
            },
        }

    def execute(self, *, user: User, limit: int = 5, **kwargs) -> Any:
        company = getattr(user, 'company', None)
        if not company:
            return []

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
