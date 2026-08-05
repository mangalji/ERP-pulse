"""
Benchmark and quality metrics service for the IDP engine.

Records ``OCRQualityMetric`` rows for each processed document so the
Quality Dashboard and future benchmarking APIs can aggregate accuracy
and processing statistics by document type / vendor. This service is
only a writer — it exposes no benchmark APIs, per project scope.
"""

from __future__ import annotations

from ocr.models import OCRQualityMetric, OCRUpload
from ocr.utils import logger


class BenchmarkService:
    """
    Record and summarise quality metrics for the IDP pipeline.

    The pipeline calls ``record()`` once per processed document. The
    ``summarise`` helpers compute lightweight aggregates used by the
    Quality Dashboard.
    """

    def record(
        self,
        *,
        upload: OCRUpload,
        user,
        company=None,
        document_type: str = '',
        vendor_name: str = '',
        processing_time_ms: int = 0,
        overall_confidence: float = 0.0,
        success: bool = False,
        failure_reason: str = '',
        validation_failures: int = 0,
        ocr_accuracy: float = 0.0,
        extraction_accuracy: float = 0.0,
    ) -> OCRQualityMetric:
        """
        Persist a single quality metric for a processed document.

        Args:
            upload: The processed ``OCRUpload``.
            user: The user who owns the document.
            company: Optional company (tenant) context.
            document_type: Detected document type.
            vendor_name: Vendor name extracted from the document.
            processing_time_ms: Total pipeline duration.
            overall_confidence: Overall extraction confidence (0-1).
            success: Whether the pipeline completed successfully.
            failure_reason: Failure message if unsuccessful.
            validation_failures: Number of validation failures.
            ocr_accuracy: OCR accuracy score (0-1).
            extraction_accuracy: Extraction accuracy score (0-1).

        Returns:
            The created ``OCRQualityMetric`` instance.
        """
        metric = OCRQualityMetric.objects.create(
            upload=upload,
            user=user,
            company=company,
            document_type=document_type,
            vendor_name=vendor_name,
            processing_time_ms=processing_time_ms,
            overall_confidence=overall_confidence,
            success=success,
            failure_reason=failure_reason,
            validation_failures=validation_failures,
            ocr_accuracy=ocr_accuracy,
            extraction_accuracy=extraction_accuracy,
        )
        logger.info(
            'Quality metric recorded — upload=%s success=%s confidence=%.2f time=%dms',
            upload.id,
            success,
            overall_confidence,
            processing_time_ms,
        )
        return metric

    def summarise(self, *, user=None, company=None, document_type: str | None = None) -> dict:
        """
        Summarise quality metrics with simple aggregates.

        Uses Django ORM aggregation (no benchmarking/external calls).
        Filters by ``user``, ``company``, or ``document_type`` when
        provided.

        Args:
            user: Optional user filter.
            company: Optional company filter.
            document_type: Optional document type filter.

        Returns:
            A dict with counts and average scores.
        """
        qs = OCRQualityMetric.objects.all()
        if user is not None:
            qs = qs.filter(user=user)
        if company is not None:
            qs = qs.filter(company=company)
        if document_type:
            qs = qs.filter(document_type=document_type)

        from django.db.models import Avg, Count, Q

        summary = qs.aggregate(
            total=Count('id'),
            success=Count('id', filter=Q(success=True)),
            failure=Count('id', filter=Q(success=False)),
            avg_confidence=Avg('overall_confidence'),
            avg_processing_time_ms=Avg('processing_time_ms'),
            avg_extraction_accuracy=Avg('extraction_accuracy'),
        )
        return {
            'total': summary['total'],
            'success': summary['success'],
            'failure': summary['failure'],
            'avg_confidence': round(summary['avg_confidence'] or 0.0, 4),
            'avg_processing_time_ms': round(summary['avg_processing_time_ms'] or 0.0, 2),
            'avg_extraction_accuracy': round(summary['avg_extraction_accuracy'] or 0.0, 4),
        }


benchmark_service = BenchmarkService()
