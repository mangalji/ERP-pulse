"""
API views for the OCR application.

Views are thin: they validate input via a serializer, delegate to
``OCRService``, and return the standard response envelope. No business
logic lives here.
"""

from __future__ import annotations

from django.db.models import Q,Count
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from common.utils.response import success_response
from rest_framework.response import Response
from ocr.models import OCRDocument, OCRDocumentVersion, OCRUpload, OCRBatch
from ocr.serializers import (
    DocumentHistorySerializer,
    DocumentVersionSerializer,
    UploadSerializer,
    UploadResponseSerializer,
    OCRDocumentHistorySerializer,
    OCRHistoryListSerializer,
    OCRHistoryVersionSerializer,
    OCRBatchHistorySerializer,
    OCRBatchHistoryItemSerializer,
    OCRHistoryEntrySerializer,
    OCRHistoryFileSerializer,
)
from ocr.services import ocr_service
from ocr.tasks import process_document_task
from ocr.utils import logger


def _is_company_admin(user) -> bool:
    """Company Admin role can see all OCR records belonging to the user's company."""

    if getattr(user, "is_superuser", False):
        return True

    if not getattr(user, "company_id", None):
        return False

    if getattr(user, "is_staff", False):
        return True
    return user.user_roles.filter(
        role__name__iexact='Company Admin',
    ).exists()

def _visible_batch_queryset(user):
    qs = OCRBatch.objects.all()

    if _is_company_admin(user):
        return qs.filter(company=user.company)

    return qs.filter(
        user=user,
        company=user.company,
    )


def _visible_document_queryset(user):
    qs = OCRDocument.objects.all()

    if _is_company_admin(user):
        return qs.filter(company=user.company)

    return qs.filter(
        user=user,
        company=user.company,
    )


def _user_display_name(user):
    if not user:
        return None
    full_name = " ".join(
        part for part in [
            getattr(user, "first_name", ""),
            getattr(user, "last_name", ""),
        ]
        if part
    ).strip()
    return full_name or getattr(user, "email", None)


def _batch_scope(user):
    """
    Employee: own batches only.
    Company Admin: all batches in the same company.
    """
    if _is_company_admin(user):
        return OCRBatch.objects.filter(company_id=user.company_id)
    return OCRBatch.objects.filter(user_id=user.id)


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

        task = getattr(process_document_task, "delay", None)
        if task is not None:
            task(upload.id,request.user.id)
        else:
            process_document_task(upload.id,request.user.id)

        data = UploadResponseSerializer(upload).data
        data["processing_status"] = OCRUpload.Status.PROCESSING
        data["task_state"] = "PENDING"

        return success_response(
            message='Upload accepted. Processing has been queued.',
            data=data,
            status_code=status.HTTP_201_CREATED,
        ) 



def _build_upload_result(upload):
    document = getattr(upload, "document", None)
    version = None

    if document is not None:
        version = document.versions.order_by(
            "-version_number"
        ).first()

    return {
        "upload_id": upload.id,
        "document_id": document.id if document else None,
        "version_id": version.id if version else None,
        "version_number": (
            version.version_number if version else None
        ),
        "filename": upload.original_filename,
        "status": upload.status,
        "data": (
            version.normalized_json if version else None
        ),
        "error": (
            upload.failure_reason
            if upload.status == OCRUpload.Status.FAILED
            else None
        ),
    }

class OCRBatchHistoryView(APIView):
    """
    GET /api/v1/ocr/history/batches/<batch_id>/
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, batch_id):
        try:
            batch = (
                _visible_batch_queryset(request.user)
                .select_related("user", "company")
                .prefetch_related(
                    "uploads__document__versions",
                )
                .get(pk=batch_id)
            )
        except OCRBatch.DoesNotExist as exc:
            raise NotFound("OCR batch not found.") from exc

        uploads = list(batch.uploads.all().order_by("created_at"))

        files = [
            _build_upload_result(upload)
            for upload in uploads
        ]

        completed = sum(
            1
            for upload in uploads
            if upload.status == OCRUpload.Status.COMPLETED
        )
        failed = sum(
            1
            for upload in uploads
            if upload.status == OCRUpload.Status.FAILED
        )
        processing = sum(
            1
            for upload in uploads
            if upload.status == OCRUpload.Status.PROCESSING
        )
        queued = sum(
            1
            for upload in uploads
            if upload.status == OCRUpload.Status.UPLOADED
        )

        serializer = OCRBatchHistorySerializer(
            {
                "batch_id": batch.id,
                "status": batch.status,
                "source_type": batch.source_type,
                "source_filename": batch.original_filename,
                "created_at": batch.created_at,
                "started_at": batch.started_at,
                "completed_at": batch.completed_at,
                "total_files": len(uploads),
                "queued_files": queued,
                "processing_files": processing,
                "completed_files": completed,
                "failed_files": failed,
                "owner_id": str(batch.user_id),
                "owner_name": _user_display_name(batch.user),
                "files": files,
            }
        )

        return success_response(
            message="OCR batch history fetched successfully.",
            data=serializer.data,
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
        try:
            offset = max(
                0,
                int(request.query_params.get("offset", 0)),
            )

            limit = min(
                max(
                    1,
                    int(
                        request.query_params.get(
                            "limit",
                            10,
                        )
                    ),
                ),
                10,
            )

        except (TypeError, ValueError):
            return Response(
                {
                    "detail": (
                        "offset and limit must be "
                        "valid integers."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        queryset = (
            _visible_batch_queryset(request.user)
            .select_related("user", "company")
            .prefetch_related(
                "uploads__document"
            )
            .order_by("-created_at")
        )

        results = []

        for batch in queryset:
            uploads = list(
                batch.uploads
                .all()
                .select_related("document")
                .order_by("created_at")
            )

            if not uploads:
                continue

            if len(uploads) > 1:
                results.append(
                    {
                        "type": "batch",
                        "batch_id": str(batch.id),
                        "document_id": None,
                        "upload_id": None,
                        "filename": (
                            batch.original_filename
                            or f"{len(uploads)} files"
                        ),
                        "file_count": len(uploads),
                        "status": batch.status,
                        "source_type": batch.source_type,
                        "created_at": batch.created_at,
                        "owner_id": str(
                            batch.user_id
                        ),
                        "owner_name": (
                            _user_display_name(
                                batch.user
                            )
                        ),
                    }
                )

            else:
                upload = uploads[0]
                document = getattr(
                    upload,
                    "document",
                    None,
                )

                results.append(
                    {
                        "type": "single",
                        "batch_id": str(batch.id),
                        "document_id": (
                            str(document.id)
                            if document
                            else None
                        ),
                        "upload_id": str(
                            upload.id
                        ),
                        "filename": (
                            upload.original_filename
                        ),
                        "file_count": 1,
                        "status": upload.status,
                        "source_type": batch.source_type,
                        "created_at": batch.created_at,
                        "owner_id": str(
                            batch.user_id
                        ),
                        "owner_name": (
                            _user_display_name(
                                batch.user
                            )
                        ),
                    }
                )

        results.sort(
            key=lambda item: item["created_at"],
            reverse=True,
        )

        total = len(results)

        page_results = results[
            offset : offset + limit
        ]

        serializer = OCRHistoryEntrySerializer(
            page_results,
            many=True,
        )

        return success_response(
            message="OCR history fetched successfully.",
            data={
                "results": serializer.data,
                "count": total,
                "offset": offset,
                "limit": limit,
                "next_offset": (
                    offset + limit
                    if offset + limit < total
                    else None
                ),
                "previous_offset": (
                    max(
                        0,
                        offset - limit,
                    )
                    if offset > 0
                    else None
                ),
            },
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
                _visible_document_queryset(request.user)
                .prefetch_related("versions")
                .get(pk=document_id)
            )
        except OCRDocument.DoesNotExist as exc:
            raise NotFound("Document not found.") from exc
        versions = list(
            document.versions.all().order_by("version_number")
        )
        serializer = DocumentHistorySerializer(
            {
                "id": document.id,
                "document_type": document.document_type,
                "status": document.status,
                "current_version": document.current_version,
                "overall_confidence": document.overall_confidence,
                "processing_metadata": document.processing_metadata,
                "versions": versions,
            }
        )
        return success_response(
            message="Document history fetched successfully.",
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
            document = _visible_document_queryset(
                request.user
            ).get(pk=document_id)
        except OCRDocument.DoesNotExist as exc:
            raise NotFound("Document not found.") from exc

        try:
            version_obj = document.versions.get(
                version_number=version
            )
        except OCRDocumentVersion.DoesNotExist as exc:
            raise NotFound(
                "Document version not found."
            ) from exc

        serializer = DocumentVersionSerializer(version_obj)

        return success_response(
            message="Document version fetched successfully.",
            data=serializer.data,
        )