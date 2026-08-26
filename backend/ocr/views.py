"""
API views for the OCR application.

Views are thin: they validate input via a serializer, delegate to
``OCRService``, and return the standard response envelope. No business
logic lives here.
"""

from __future__ import annotations

import json
import redis

from django.conf import settings

from django.db.models import Q,Count
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from common.utils.response import success_response
from rest_framework.response import Response
from ocr.models import OCRDocument, OCRDocumentVersion, OCRUpload, OCRBatch, OCRExtractionTemplate, OCRValidationResult
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
    OCRSaveRequestSerializer,
    OCRExtractionTemplateSerializer,
    OCRExtractionTemplateCreateSerializer,
)
from ocr.services import ocr_service
from ocr.services.extraction_persistence import persist_extraction
from ocr.notebook_extraction_service import get_standard_field_catalog
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




def _get_live_ocr_result(upload_id):
    """Read the unsaved AI extraction result from Redis."""
    try:
        client = redis.Redis.from_url(
            settings.CELERY_BROKER_URL,
            decode_responses=True,
        )
        cached = client.get(f"erp-pulse:ocr:live:{upload_id}")
        if not cached:
            return None
        result = json.loads(cached)
        return result if isinstance(result, dict) else None
    except Exception:
        logger.exception(
            "Failed to read live OCR result during save — upload_id=%s",
            upload_id,
        )
        return None

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

        process_document_task.delay(str(upload.id), request.user.id)

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

    if document is not None and upload.status == OCRUpload.Status.COMPLETED:
        document = (
            OCRDocument.objects.filter(upload_id=upload.id).order_by("-created_at").first()
        )
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

    Returns one row per uploaded file, newest first. Validation state is
    derived from the latest validation result for the current OCR version.

    OCRUpload exposes the OCRDocument through the ``document`` relation;
    there is no direct ``OCRUpload.document_id`` model field.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            offset = max(0, int(request.query_params.get("offset", 0)))
            limit = min(
                max(1, int(request.query_params.get("limit", 100))),
                100,
            )
        except (TypeError, ValueError):
            return Response(
                {"detail": "offset and limit must be valid integers."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        uploads = list(
            OCRUpload.objects
            .filter(batch__in=_visible_batch_queryset(request.user))
            .select_related("batch", "document", "user")
            .order_by("-created_at")
        )

        documents = {}
        current_versions = {}

        for upload in uploads:
            document = getattr(upload, "document", None)
            documents[upload.id] = document

            if document is not None:
                current_versions[document.id] = (
                    OCRDocumentVersion.objects
                    .filter(document_id=document.id)
                    .order_by("-version_number")
                    .first()
                )

        document_ids = [
            document.id
            for document in documents.values()
            if document is not None
        ]

        latest_validation = {}

        if document_ids:
            validations = (
                OCRValidationResult.objects
                .filter(document_id__in=document_ids)
                .select_related("version")
                .order_by("document_id", "-created_at")
            )

            for validation in validations:
                document_id = validation.document_id
                current_version = current_versions.get(document_id)

                # Never expose a validation result belonging to an older
                # OCR version as the current document's validation state.
                if (
                    current_version is not None
                    and validation.version_id != current_version.id
                ):
                    continue

                if document_id not in latest_validation:
                    latest_validation[document_id] = validation

        results = []

        for upload in uploads:
            document = documents.get(upload.id)
            validation = (
                latest_validation.get(document.id)
                if document is not None
                else None
            )

            results.append(
                {
                    "type": "single",
                    "batch_id": (
                        str(upload.batch_id)
                        if upload.batch_id
                        else None
                    ),
                    "document_id": (
                        str(document.id)
                        if document
                        else None
                    ),
                    "upload_id": str(upload.id),
                    "filename": upload.original_filename,
                    "file_count": 1,
                    "status": upload.status,
                    "source_type": getattr(
                        upload.batch,
                        "source_type",
                        None,
                    ),
                    "created_at": upload.created_at,
                    "owner_id": str(upload.user_id),
                    "owner_name": _user_display_name(upload.user),
                    "validation_status": (
                        validation.status
                        if validation
                        else None
                    ),
                    "validation_errors": (
                        validation.errors
                        if validation
                        else []
                    ),
                    "validation_id": (
                        str(validation.id)
                        if validation
                        else None
                    ),
                    "validation_updated_at": (
                        validation.created_at
                        if validation
                        else None
                    ),
                }
            )

        total = len(results)
        page_results = results[offset:offset + limit]

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
                    max(0, offset - limit)
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
                "requested_fields": (
                    getattr(getattr(document.upload, 'batch', None), 'requested_fields_json', None)
                    if document.upload_id
                    else None
                ),
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

class OCRReviewSaveView(APIView):
    """
    Save a user-reviewed OCR result.

    New extraction:
        upload_id -> live Redis result is the original AI result.

    Existing document:
        document_id -> latest saved version is the original result.

    The submitted `data` is always treated as the user's reviewed result.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = OCRSaveRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        upload_id = serializer.validated_data.get("upload_id")
        document_id = serializer.validated_data.get("document_id")
        reviewed_result = serializer.validated_data["data"]

        try:
            if upload_id:
                return self._save_new_extraction(
                    request.user,
                    upload_id,
                    reviewed_result,
                )

            return self._save_existing_document(
                request.user,
                document_id,
                reviewed_result,
            )

        except PermissionError as exc:
            logger.warning(
                "OCR save permission denied — user=%s upload=%s document=%s",
                request.user.id,
                upload_id,
                document_id,
            )

            return Response(
                {"detail": str(exc)},
                status=status.HTTP_403_FORBIDDEN,
            )

        except OCRUpload.DoesNotExist:
            return Response(
                {"detail": "OCR upload not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        except OCRDocument.DoesNotExist:
            return Response(
                {"detail": "OCR document not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        except ValueError as exc:
            logger.warning(
                "OCR save validation failed — user=%s error=%s",
                request.user.id,
                exc,
            )

            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception as exc:
            logger.exception(
                "OCR save failed — user=%s upload=%s document=%s",
                request.user.id,
                upload_id,
                document_id,
            )

            return Response(
                {
                    "detail": "Unable to save OCR result.",
                    "error": str(exc),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def _save_new_extraction(self, user, upload_id, reviewed_result):
        upload = OCRUpload.objects.select_related(
            "user",
            "batch",
        ).get(pk=upload_id)

        if upload.user_id != user.id:
            raise PermissionError(
                "You do not have permission to save this OCR result."
            )

        original_result = _get_live_ocr_result(upload_id)

        if original_result is None:
            raise ValueError(
                "The live OCR result is no longer available. "
                "Please re-run OCR before saving."
            )

        document, version = persist_extraction(
            upload=upload,
            user=user,
            result=original_result,
            reviewed_result=reviewed_result,
        )

        return success_response(
            message="OCR result saved successfully.",
            data={
                "document_id": str(document.id),
                "version_id": str(version.id),
                "version_number": version.version_number,
                "status": document.status,
                "data": reviewed_result,
            },
            status_code=status.HTTP_200_OK,
        )

    def _save_existing_document(self, user, document_id, reviewed_result):
        document = _visible_document_queryset(user).get(
            pk=document_id,
        )

        latest = (
            document.versions
            .order_by("-version_number")
            .first()
        )

        if latest is None:
            raise ValueError(
                "No saved OCR version exists for this document."
            )

        original_result = latest.normalized_json

        upload = document.upload

        if upload is None:
            raise ValueError(
                "The OCR document is not linked to its original upload."
            )

        document, version = persist_extraction(
            upload=upload,
            user=user,
            result=original_result,
            reviewed_result=reviewed_result,
        )

        return success_response(
            message="OCR result updated successfully.",
            data={
                "document_id": str(document.id),
                "version_id": str(version.id),
                "version_number": version.version_number,
                "status": document.status,
                "data": reviewed_result,
            },
            status_code=status.HTTP_200_OK,
        )

class OCRExtractionTemplateListView(APIView):
    """List/create company-scoped dynamic OCR extraction templates."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = OCRExtractionTemplate.objects.filter(
            company=request.user.company
        ).order_by("name")
        serializer = OCRExtractionTemplateSerializer(queryset, many=True)
        return success_response(
            message="Extraction templates fetched successfully.",
            data=serializer.data,
        )

    def post(self, request):
        serializer = OCRExtractionTemplateCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        name = serializer.validated_data["name"].strip()
        fields_config = serializer.validated_data["fields_config"]
        template, created = OCRExtractionTemplate.objects.update_or_create(
            company=request.user.company,
            name=name,
            defaults={
                "fields_config": fields_config,
                "created_by": request.user,
            },
        )
        return success_response(
            message=(
                "Extraction template saved successfully."
                if created
                else "Extraction template updated successfully."
            ),
            data=OCRExtractionTemplateSerializer(template).data,
            status_code=status.HTTP_201_CREATED,
        )


class OCRExtractionTemplateDetailView(APIView):
    """Retrieve/delete a company-scoped extraction template."""

    permission_classes = [IsAuthenticated]

    def _get_template(self, request, template_id):
        try:
            return OCRExtractionTemplate.objects.get(
                pk=template_id,
                company=request.user.company,
            )
        except (OCRExtractionTemplate.DoesNotExist, ValueError, TypeError):
            raise NotFound("Extraction template not found.")

    def get(self, request, template_id):
        template = self._get_template(request, template_id)
        return success_response(
            message="Extraction template fetched successfully.",
            data=OCRExtractionTemplateSerializer(template).data,
        )

    def delete(self, request, template_id):
        template = self._get_template(request, template_id)
        template.delete()
        return success_response(
            message="Extraction template deleted successfully.",
            data=None,
        )


class OCRStandardFieldsView(APIView):
    """Return the standard dynamic OCR extraction-field catalogue."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return success_response(
            message="Standard extraction fields fetched successfully.",
            data=get_standard_field_catalog(),
        )
