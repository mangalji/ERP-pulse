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
        task = process_document_task.delay(upload.id, request.user.id)
        logger.info(
            'OCR task dispatched — upload_id=%s user=%s task=%s',
            upload.id, request.user.id, task.id,
        )

        response_serializer = UploadResponseSerializer(upload)
        data = response_serializer.data
        data['processing_status'] = OCRUpload.Status.PROCESSING
        data['task_state'] = 'PENDING'

        return success_response(
            message='Upload accepted. Processing has been queued.',
            data=data,
            status_code=status.HTTP_202_ACCEPTED,
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
            document = OCRDocument.objects.prefetch_related(
                'versions'
            ).get(pk=document_id, user=request.user)
        except OCRDocument.DoesNotExist as exc:
            raise NotFound('Document not found.') from exc

        versions = list(document.versions.all().order_by('version_number'))
        serializer = DocumentHistorySerializer({
            'id': document.id,
            'document_type': document.document_type,
            'status': document.status,
            'current_version': document.current_version,
            'overall_confidence': document.overall_confidence,
            'processing_metadata': document.processing_metadata,
            'versions': versions,
        })
        return success_response(
            message='Document history fetched successfully.',
            data=serializer.data,
        )


class DocumentVersionView(APIView):
    """
    GET /api/v1/ocr/documents/{id}/history/{version}/

    Returns a single immutable version snapshot of a document.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, document_id, version):
        try:
            document = OCRDocument.objects.get(pk=document_id, user=request.user)
        except OCRDocument.DoesNotExist as exc:
            raise NotFound('Document not found.') from exc

        try:
            version_obj = document.versions.get(version_number=version)
        except OCRDocumentVersion.DoesNotExist as exc:
            raise NotFound('Document version not found.') from exc

        serializer = DocumentVersionSerializer(version_obj)
        return success_response(
            message='Document version fetched successfully.',
            data=serializer.data,
        )
