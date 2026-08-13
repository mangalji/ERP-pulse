"""
API views for the OCR application.

Views are thin: they validate input via a serializer, delegate to
``OCRService``, and return the standard response envelope. No business
logic lives here.
"""

from __future__ import annotations

from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from common.utils.response import success_response
from ocr.models import OCRDocument, OCRDocumentVersion, OCRUpload
from ocr.serializers import (
    DocumentHistorySerializer,
    DocumentVersionSerializer,
    UploadSerializer,
    UploadResponseSerializer,
    OCRDocumentHistorySerializer,
    OCRHistoryListSerializer,
    OCRHistoryVersionSerializer,
)
from ocr.services import ocr_service
from ocr.tasks import process_document_task
from ocr.utils import logger


class UploadView(APIView):
    """
    POST /api/v1/ocr/upload/

    Accepts an invoice file (PDF, PNG, JPG, JPEG, or WEBP; max 10 MB),
    validates it via ``UploadSerializer``, delegates storage to
    ``OCRService.upload()``, then dispatches the asynchronous IDP
    pipeline via ``process_document_task.delay()``.

    Returns HTTP 202 Accepted with the upload metadata and the Celery
    task state, since processing runs asynchronously in the worker.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = UploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        upload = ocr_service.upload(
            file=serializer.validated_data['file'],
            user=request.user,
        )

        # Dispatch the async pipeline — never run synchronously.
        if hasattr(process_document_task, 'delay'):
            task = process_document_task.delay(upload.id, request.user.id)
            logger.info(
                'OCR task dispatched — upload_id=%s user=%s task=%s',
                upload.id, request.user.id, task.id,
            )
        else:
            logger.warning(
                'Celery not available; running OCR synchronously for upload_id=%s user=%s',
                upload.id, request.user.id,
            )
            process_document_task(upload.id, request.user.id)

        response_serializer = UploadResponseSerializer(upload)
        data = response_serializer.data
        data['processing_status'] = OCRUpload.Status.PROCESSING
        data['task_state'] = 'PENDING'

        return success_response(
            message='Upload accepted. Processing has been queued.',
            data=data,
            status_code=status.HTTP_201_CREATED,
        )


class OCRHistoryListView(APIView):
    """
    GET /api/v1/ocr/history/

    Returns the authenticated user's OCR uploads, newest first.
    Failed/processing uploads are included so the history reflects
    everything the user submitted.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        uploads = (
            OCRUpload.objects
            .filter(user=request.user)
            .select_related('document')
            .order_by('-created_at')[:100]
        )

        results = []
        for upload in uploads:
            document = getattr(upload, 'document', None)
            results.append(
                {
                    'upload_id': upload.id,
                    'document_id': document.id if document else None,
                    'filename': upload.original_filename,
                    'status': upload.status,
                    'document_type': document.document_type if document else None,
                    'created_at': upload.created_at,
                }
            )

        serializer = OCRHistoryListSerializer(results, many=True)
        return success_response(
            message='OCR history fetched successfully.',
            data=serializer.data,
        )


class DocumentHistoryView(APIView):
    """
    GET /api/v1/ocr/documents/{id}/history/

    Returns the document summary plus its ordered list of immutable
    version snapshots.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, document_id):
        try:
            document = (
                OCRDocument.objects
                .select_related('upload')
                .prefetch_related('versions__line_items')
                .get(pk=document_id, user=request.user)
            )
        except OCRDocument.DoesNotExist as exc:
            raise NotFound('Document not found.') from exc

        versions = list(document.versions.all().order_by('version_number'))
        serializer = OCRDocumentHistorySerializer(
        {
            'id': document.id,
            'upload_id': document.upload_id,
            'filename': (
                document.upload.original_filename
                if document.upload_id and document.upload
                else None
            ),
            'document_type': document.document_type,
            'status': document.status,
            'current_version': document.current_version,
            'overall_confidence': document.overall_confidence,
            'processing_metadata': document.processing_metadata,
            'versions': versions,
        }
    )

        return success_response(
            message='Document history fetched successfully.',
            data=serializer.data,
        )


class DocumentVersionView(APIView):
    """
    GET /api/v1/ocr/documents/{id}/history/{version}/

    Returns a single immutable version snapshot with upload metadata.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, document_id, version):
        try:
            document = (
                OCRDocument.objects
                .select_related('upload')
                .get(pk=document_id, user=request.user)
            )
        except OCRDocument.DoesNotExist as exc:
            raise NotFound('Document not found.') from exc

        try:
            version_obj = (
                document.versions
                .prefetch_related('line_items')
                .get(version_number=version)
            )
        except OCRDocumentVersion.DoesNotExist as exc:
            raise NotFound('Document version not found.') from exc

        payload = {
            'id': version_obj.id,
            'version_number': version_obj.version_number,
            'invoice_number': version_obj.invoice_number,
            'invoice_date': version_obj.invoice_date,
            'due_date': version_obj.due_date,
            'vendor_name': version_obj.vendor_name,
            'customer_name': version_obj.customer_name,
            'subsidiary': version_obj.subsidiary,
            'currency': version_obj.currency,
            'subtotal': version_obj.subtotal,
            'tax_amount': version_obj.tax_amount,
            'tax_rate': version_obj.tax_rate,
            'total_amount': version_obj.total_amount,
            'payment_terms': version_obj.payment_terms,
            'line_items': version_obj.line_items.all().order_by('line_number'),
            'normalized_json': version_obj.normalized_json,
            'created_at': version_obj.created_at,
        }

        serializer = OCRHistoryVersionSerializer(payload)

        data = serializer.data
        data['upload_id'] = str(document.upload_id) if document.upload_id else None
        data['filename'] = (
            document.upload.original_filename
            if document.upload_id and document.upload
            else None
        )
        data['document_status'] = document.status

        return success_response(
            message='Document version fetched successfully.',
            data=data,
        )
        
