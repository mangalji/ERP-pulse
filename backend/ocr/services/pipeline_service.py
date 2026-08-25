"""
IDP pipeline orchestration service.

Orchestrates the full document understanding pipeline in the correct
order, reusing the existing OCR building blocks (PDF conversion, image
preprocessing, Gemini extraction, schema validation) and the isolated
services (validation, classification, layout, normalization, document
persistence, business-rule validation, benchmark metrics).

This service is intentionally an *orchestrator only*. It does not
implement per-stage retry logic — that is delegated to the Celery
worker (``tasks.py``). It records a stage timeline in
``processing_metadata`` so pipelines can be traced end-to-end.
"""

from __future__ import annotations

import time

from django.db import transaction
from django.utils import timezone

from ocr.exceptions import (
    OCRExtractionFailedException,
    OCRServiceException,
)
from ocr.models import (
    OCRDocument,
    OCRDocumentStatus,
    OCRUpload,
)
from ocr.services.benchmark_service import benchmark_service
from ocr.services.classification_service import classification_service
from ocr.services.document_service import document_service
from ocr.services.layout_service import layout_service
from ocr.services.normalization_service import normalization_service
from ocr.services.validation_service import validation_service
from ocr.pdf_processor import pdf_processor
from ocr.extraction_service import ocr_extraction_service
from ocr.adapters import get_adapter
from ocr.utils import logger


class IDPPipelineService:
    """
    Orchestrate the IDP document pipeline.

    The pipeline runs synchronously when invoked directly. A Celery
    task (in ``tasks.py``) wraps this service for async processing.
    """

    def process_upload(self, *, upload_id: str, user) -> dict:
        """
        Run the full pipeline on an upload.

        Stages (each recorded in ``processing_metadata``):
        1. Load upload + validate
        2. Normalize document via format adapter → images
        3. Extract via Gemini + schema validate
        4. Classify + layout analyze + normalize
        5. Business-rule validation
        6. Persist document + versions + pages
        7. Record quality metric

        Args:
            upload_id: UUID of the ``OCRUpload``.
            user: The authenticated user.

        Returns:
            A pipeline result dict.

        Raises:
            OCRServiceException: If a critical stage fails.
        """
        start = time.perf_counter()
        logger.info('IDP pipeline started — upload=%s user=%s', upload_id, user.id)

        upload = self._get_upload(upload_id, user)
        timeline: list[dict] = []
        document = None
        adapter = None

        try:
            # Stage: normalize document via format adapter
            with self._stage('render', timeline):
                adapter = get_adapter(upload.file.path, str(upload.id))
                normalized = adapter.normalize()
                images = normalized.get('pages', [])

            # Stage: extract + validate
            with self._stage('extract', timeline):
                extraction = self._extract(upload, user, images)

            # Stage: classify + layout + normalize
            with self._stage('analyze', timeline):
                analysis = self._analyze(extraction)

            # Stage: business-rule validation
            with self._stage('validate', timeline):
                validation = validation_service.validate_business_rules(
                    normalized=analysis['normalized'],
                )
                analysis['validation'] = validation

            # Stage: persist
            with self._stage('persist', timeline):
                document = self._persist(upload, user, extraction, analysis)

            # Record the full stage timeline on the document.
            self._record_timeline(document, timeline)

            # Stage: record metric
            with self._stage('benchmark', timeline):
                benchmark_service.record(
                    upload=upload,
                    user=user,
                    company=getattr(upload, 'company', None),
                    document_type=analysis['document_type'],
                    processing_time_ms=round((time.perf_counter() - start) * 1000, 2),
                    overall_confidence=analysis['confidence'].get('overall') or 0.0,
                    success=True,
                    validation_failures=len(validation.get('errors', [])),
                    extraction_accuracy=analysis['confidence'].get('overall') or 0.0,
                )

            duration_ms = (time.perf_counter() - start) * 1000
            logger.info(
                'IDP pipeline completed — upload=%s document=%s duration=%.2fms',
                upload.id, document.id, duration_ms,
            )
            return {
                'document_id': str(document.id),
                'upload_id': str(upload.id),
                'status': document.status,
                'processing_time_ms': round(duration_ms, 2),
                'validation_errors': validation.get('errors', []),
            }
        except OCRServiceException:
            if document is not None:
                self._record_timeline(document, timeline)
            raise
        except Exception as exc:
            logger.exception('IDP pipeline failed — upload=%s', upload_id)
            self._mark_failed(upload, exc)
            if document is not None:
                self._record_timeline(document, timeline)
            raise OCRExtractionFailedException(
                f'IDP pipeline failed: {exc}'
            ) from exc
        finally:
            if adapter is not None:
                try:
                    adapter.cleanup()
                except Exception:
                    logger.exception(
                        'Adapter cleanup failed for upload %s.', upload_id
                    )
            pdf_processor.cleanup(upload_id)

            try:
                rendered_dir = Path('/tmp/ocr_rendered')
                if rendered_dir.exists():
                    for f in rendered_dir.glob(f'{upload_id}_*'):
                        try:
                            f.unlink()
                        except Exception:
                            pass
            except Exception:
                logger.exception(
                    'Rendered image cleanup failed for upload %s.', upload_id
                )

    # ── Stage helpers ──────────────────────────────────────────────

    class _stage:
        """Context manager that records a stage's start/end/status."""

        def __init__(self, name: str, timeline: list):
            self.name = name
            self.timeline = timeline
            self._start = None

        def __enter__(self):
            self._start = timezone.now().isoformat()
            return self

        def __exit__(self, exc_type, exc, tb):
            entry = {
                'stage': self.name,
                'started_at': self._start,
                'ended_at': timezone.now().isoformat(),
                'status': 'failed' if exc_type else 'completed',
            }
            if exc is not None:
                entry['error'] = str(exc)[:500]
            self.timeline.append(entry)
            return False  # Do not swallow exceptions.

    @staticmethod
    def _record_timeline(document: OCRDocument, timeline: list) -> None:
        """Persist the stage timeline into the document's metadata."""
        if not timeline:
            return
        try:
            metadata = document.processing_metadata or {}
            metadata['current_stage'] = 'completed'
            metadata['stage_timeline'] = timeline
            document.processing_metadata = metadata
            document.save(update_fields=['processing_metadata'])
        except Exception:
            logger.exception('Failed to record pipeline timeline for document %s.', document.id)

    # ── Stages ─────────────────────────────────────────────────────

    @staticmethod
    def _get_upload(upload_id: str, user) -> OCRUpload:
        """Load and validate the upload."""
        try:
            upload = OCRUpload.objects.select_related('user').get(pk=upload_id)
        except OCRUpload.DoesNotExist as exc:
            raise OCRServiceException('Upload not found.') from exc
        if upload.user_id != user.id:
            raise OCRServiceException('Upload does not belong to this user.')
        return upload

    def _render_images(self, upload: OCRUpload) -> list:
        adapter = get_adapter(upload.file.path, str(upload.id))
        result = adapter.normalize()
        return result.get('pages', [])

    def _extract(self, upload: OCRUpload, user, images) -> dict:
        """
        Extract structured data from all rendered images.

        For multi-page documents (PDF, DOCX, etc.), each page/image is
        extracted independently and the results are merged into a single
        canonical result. Header fields prefer the first non-null value
        across pages; line items are concatenated.
        """
        requested_fields = None
        if upload.batch and isinstance(upload.batch.requested_fields_json, dict):
            requested_fields = upload.batch.requested_fields_json

        if not images:
            raise OCRServiceException(
                'No images available for extraction.'
            )

        if len(images) == 1:
            return ocr_extraction_service.extract(
                _FakeUpload(upload, images[0]),
                user,
                requested_fields=requested_fields,
            )

        page_results = []
        for idx, image_path in enumerate(images):
            try:
                result = ocr_extraction_service.extract(
                    _FakeUpload(upload, image_path),
                    user,
                    requested_fields=requested_fields,
                )
                page_results.append(result)
            except Exception as exc:
                logger.exception(
                    'Page extraction failed — upload=%s page=%d',
                    upload.id,
                    idx,
                )
                raise

        return self._merge_extraction_results(page_results)

    def _merge_extraction_results(self, page_results: list[dict]) -> dict:
        """
        Merge extraction results from multiple pages into a single result.

        Strategy:
        - Header fields (including custom): first non-null/non-empty value
        - Line items (including custom): concatenate all lists
        - raw_text: concatenate with page separators
        - confidence/image_quality: use first page's values
        """
        if not page_results:
            raise OCRServiceException('No page results to merge.')

        if len(page_results) == 1:
            return page_results[0]

        base = page_results[0].copy()
        base_data = dict(base.get('data', {}))

        all_keys = set()
        for result in page_results:
            all_keys.update(result.get('data', {}).keys())

        for key in all_keys:
            values = []
            for result in page_results:
                val = result.get('data', {}).get(key)
                if val is not None:
                    values.append(val)

            if key == 'line_items' or any(isinstance(v, list) for v in values):
                merged_items = []
                for val in values:
                    if isinstance(val, list):
                        merged_items.extend(val)
                base_data[key] = merged_items
            elif key == 'raw_text':
                texts = [str(v) for v in values if v]
                base_data[key] = '\n\n---PAGE BREAK---\n\n'.join(texts) if texts else None
            else:
                for val in values:
                    if val is not None and val != '' and val != []:
                        base_data[key] = val
                        break
                else:
                    base_data[key] = values[0] if values else None

        base['data'] = base_data
        return base

    def _analyze(self, extraction: dict) -> dict:
        """Classify, analyze layout, and normalize the extraction."""
        data = extraction.get('data', {})

        # Classification from text (fall back to raw text/confidence).
        raw_text = data.get('raw_text', '')
        classification = classification_service.classify(raw_text=raw_text)
        document_type = classification['document_type']

        layout = layout_service.analyze(raw_text=raw_text)

        normalized = normalization_service.normalize(
            raw=data,
            document_type=document_type,
        )

        return {
            'document_type': document_type,
            'classification_confidence': classification['confidence'],
            'layout': layout,
            'normalized': normalized,
            'confidence': data.get('confidence', {}),
            'raw_text': raw_text,
        }

    @transaction.atomic
    def _persist(self, upload, user, extraction, analysis) -> object:
        """Persist document, version, and pages."""
        document = document_service.create_document(
            upload=upload,
            user=user,
            company=getattr(upload, 'company', None),
            document_type=analysis['document_type'],
            status=OCRDocumentStatus.EXTRACTED,
            page_count=1,
            overall_confidence=analysis['confidence'].get('overall'),
        )

        document_service.save_document(
            document=document,
            raw_text=analysis['raw_text'],
            layout_blocks=analysis['layout'].get('blocks', {}),
            normalized_json=analysis['normalized'],
            confidence=analysis['confidence'],
            status=OCRDocumentStatus.EXTRACTED,
        )

        document_service.create_pages(
            document=document,
            pages=[{
                'page_number': 1,
                'raw_text': analysis['raw_text'],
                'layout_blocks': analysis['layout'].get('blocks', {}),
            }],
        )
        return document

    @staticmethod
    def _mark_failed(upload, exc) -> None:
        """Mark the upload as failed with a reason."""
        try:
            upload.status = OCRUpload.Status.FAILED
            upload.failure_session = str(exc)[:500]
            upload.save(update_fields=['status', 'failure_session'])
        except Exception:
            logger.exception('Failed to mark upload %s as failed.', upload.id)


class _FakeUpload:
    """
    Minimal adapter exposing the path attribute the extraction service
    expects. The real ``OCRUpload`` is used by the document persistence
    stage; this adapter only surfaces the rendered image path for the
    extraction service.
    """

    def __init__(self, upload, image_path):
        self._upload = upload
        self.path = image_path

    @property
    def id(self):
        return self._upload.id


idp_pipeline_service = IDPPipelineService()
