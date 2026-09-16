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
from django.http import FileResponse
from django.db.models import Q,Count
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from common.common_utils import success_response
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
from ocr.exceptions import OCRException
from ocr.services import ocr_service
from ocr.services.extraction_persistence import persist_extraction
from ocr.notebook_extraction_service import get_standard_field_catalog, resolve_field_config
from ocr.tasks import process_document_task, process_ocr_upload_task
from ocr.utils import logger
from ocr.services.zip_upload_service import (
    ZipValidationError,
    extract_supported_files_from_zip,
)

def _parse_requested_fields(raw) -> dict | None:
    """
    Normalize the user-supplied dynamic extraction configuration.

    Accepts either a JSON object or a JSON-encoded string.
    Returns None when nothing usable was supplied.
    """
    if raw is None:
        return None

    if isinstance(raw, str):
        raw = raw.strip()
        if not raw:
            return None

        try:
            raw = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            raise ValueError(
                "requested_fields must be a valid JSON object."
            )

    if not isinstance(raw, dict):
        raise ValueError(
            "requested_fields must be a JSON object."
        )

    return raw


def _resolve_template_config(template_id, user) -> dict:
    """Load a saved extraction template's config (company-scoped)."""
    if not template_id:
        raise ValueError("Invalid template identifier.")

    try:
        template = OCRExtractionTemplate.objects.get(
            pk=template_id,
            company=user.company,
        )
    except (
        OCRExtractionTemplate.DoesNotExist,
        ValueError,
        TypeError,
    ):
        raise ValueError("Extraction template not found.")

    config = template.fields_config
    if not isinstance(config, dict):
        config = {}

    return config


def _build_requested_fields(request) -> dict | None:
    """
    Resolve the effective requested_fields from the upload request.

    An explicit template_id takes precedence over inline
    requested_fields.
    """
    template_id = request.data.get("template_id")
    raw_requested = _parse_requested_fields(
        request.data.get("requested_fields")
    )

    if template_id:
        requested_fields = _resolve_template_config(
            template_id,
            request.user,
        )
    elif raw_requested is not None:
        requested_fields = raw_requested
    else:
        requested_fields = None

    if requested_fields:
        resolve_field_config(requested_fields)

    return requested_fields


def _is_company_admin(user) -> bool:
    """Company Admin role can see all OCR records belonging to the user's company."""

    if getattr(user, "is_superuser", False):
        return True

    if not getattr(user, "company_id", None):
        return False

    if getattr(user, "is_staff", False):
        return True

    role = getattr(user, "role", None)

    return role is not None and role.name.lower() == "company admin"

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

def _visible_upload_queryset(user):
    queryset = OCRUpload.objects.select_related(
        "user",
        "batch",
        "document",
    )

    if _is_company_admin(user):
        return queryset.filter(
            user__company_id=user.company_id,
        )

    return queryset.filter(
        user=user,
        user__company_id=user.company_id,
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
            allow_company_admin=_is_company_admin(user),
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


class OCRExtractView(APIView):
    """
    Accept one/many PDF/image files or ZIP archives.

    The HTTP request only validates/stores files and queues per-file tasks.
    Gemini extraction happens asynchronously in Celery workers.
    """

    permission_classes = [IsAuthenticated]

    def _get_uploaded_files(self, request):
        files = request.FILES.getlist("files")

        if not files:
            single_file = request.FILES.get("file")
            if single_file is not None:
                files = [single_file]

        return files

    @staticmethod
    def _is_zip(uploaded_file):
        name = (getattr(uploaded_file, "name", "") or "").lower()
        content_type = (getattr(uploaded_file, "content_type", "") or "").lower()
        return (
            name.endswith(".zip")
            or content_type in {
                "application/zip",
                "application/x-zip-compressed",
            }
        )

    def _expand_inputs(self, uploaded_files):
        expanded = []

        for uploaded_file in uploaded_files:
            if not self._is_zip(uploaded_file):
                expanded.append(uploaded_file)
                continue

            try:
                expanded.extend(
                    extract_supported_files_from_zip(uploaded_file)
                )
            except ZipValidationError:
                raise
            except OCRException as exc:
                raise
            except Exception as exc:
                raise ZipValidationError(
                    f"Unable to read ZIP archive '{uploaded_file.name}'."
                ) from exc

        if not expanded:
            raise ZipValidationError(
                "The upload contains no supported PDF/image files."
            )

        return expanded

    @staticmethod
    def _is_company_admin(user):
        if getattr(user, "is_superuser", False):
            return True

        if not getattr(user, "company_id", None):
            return False

        if getattr(user, "is_staff", False):
            return True

        role = getattr(user, "role", None)

        return role is not None and role.name.lower() == "company admin"

    def _get_batch_for_request(self, request, batch_id):
        queryset = OCRBatch.objects.prefetch_related(
            "uploads__document__versions"
        )

        if self._is_company_admin(request.user):
            queryset = queryset.filter(company=request.user.company)
        else:
            queryset = queryset.filter(
                user=request.user,
                company=request.user.company,
            )

        try:
            return queryset.get(pk=batch_id)
        except OCRBatch.DoesNotExist as exc:
            raise NotFound("OCR batch not found.") from exc

    @staticmethod
    def _serialize_upload(upload):
        version = None

        document = getattr(upload, "document", None)
        if document is not None:
            version = document.versions.order_by("-version_number").first()

        item = {
            "status": upload.status,
            "upload_id": str(upload.id),
            "document_id": str(document.id) if document else None,
            "version_id": str(version.id) if version else None,
            "version_number": version.version_number if version else None,
            "filename": upload.original_filename,
            "error": upload.failure_reason if upload.status == OCRUpload.Status.FAILED else None,
            "data": version.normalized_json if version else None,
        }

        return item

    def post(self, request):
        uploaded_files = self._get_uploaded_files(request)

        if not uploaded_files:
            return Response(
                {
                    "detail": (
                        "No files uploaded. Use the 'files' field for one or "
                        "more PDF/image files, or upload a ZIP archive."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        batch = None
        created_uploads = []

        try:
            company = getattr(request.user, "company", None)
            contains_zip = any(
                self._is_zip(uploaded_file)
                for uploaded_file in uploaded_files
            )

            actual_files = self._expand_inputs(uploaded_files)

            source_type = (
                OCRBatch.SourceType.ZIP
                if contains_zip
                else OCRBatch.SourceType.DIRECT
            )

            original_filename = (
                uploaded_files[0].name
                if contains_zip and len(uploaded_files) == 1
                else None
            )

            try:
                requested_fields = _build_requested_fields(request)
            except ValueError as exc:
                return Response(
                    {"detail": str(exc)},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            batch = OCRBatch.objects.create(
                user=request.user,
                company=company,
                source_type=source_type,
                original_filename=original_filename,
                requested_fields_json=requested_fields or {},
                status=OCRBatch.Status.PROCESSING,
                started_at=timezone.now(),
            )

            # Store every actual OCR file first. No Gemini request happens
            # inside the HTTP request.
            for actual_file in actual_files:
                upload = ocr_service.upload(
                    file=actual_file,
                    user=request.user,
                )
                upload.batch = batch
                # PROCESSING, not UPLOADED: from this point on the file is
                # queued for the Celery task below, so "work is happening"
                # from the user's perspective even before a worker actually
                # picks it up and the task itself re-confirms PROCESSING.
                # Reporting UPLOADED here was the spec's flagged bug — the
                # frontend's very first status read (this response) and
                # every poll before the task starts would show a resting
                # state while a job was already in flight.
                upload.status = OCRUpload.Status.PROCESSING
                upload.failure_reason = None
                upload.save(update_fields=["batch", "status", "failure_reason"])
                created_uploads.append(upload)

            if not created_uploads:
                raise ZipValidationError(
                    "No supported OCR files were created from this upload."
                )

            # Queue each file independently. Celery workers plus the Redis
            # limiter control actual Gemini concurrency/rate.
            queued = 0
            for upload in created_uploads:
                task = getattr(process_ocr_upload_task, "delay", None)

                if task is None:
                    # Development fallback if Celery is unavailable.
                    process_ocr_upload_task(
                        str(upload.id),
                        str(request.user.id),
                    )
                else:
                    task(
                        str(upload.id),
                        str(request.user.id),
                    )

                queued += 1

            return Response(
                {
                    "batch_id": str(batch.id),
                    "status": batch.status,
                    "source_type": batch.source_type,
                    "source_filename": batch.original_filename,
                    "total_files": len(created_uploads),
                    "queued_files": queued,
                    "files": [
                        {
                            "upload_id": str(upload.id),
                            "filename": upload.original_filename,
                            "status": upload.status,
                        }
                        for upload in created_uploads
                    ],
                },
                status=status.HTTP_202_ACCEPTED,
            )

        except ZipValidationError as exc:
            logger.warning(
                "OCR batch validation failed — user=%s error=%s",
                request.user.id,
                exc,
            )

            if batch is not None:
                batch.status = OCRBatch.Status.FAILED
                batch.completed_at = timezone.now()
                batch.save(update_fields=["status", "completed_at"])

            return Response(
                {
                    "detail": str(exc),
                    "batch_id": str(batch.id) if batch else None,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception as exc:
            logger.exception(
                "OCR batch submission failed — batch_id=%s error=%s",
                getattr(batch, "id", None),
                exc,
            )

            if batch is not None:
                batch.status = OCRBatch.Status.FAILED
                batch.completed_at = timezone.now()
                batch.save(update_fields=["status", "completed_at"])

            return Response(
                {
                    "detail": "OCR batch submission failed.",
                    "error": str(exc),
                    "batch_id": str(batch.id) if batch else None,
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class OCRUploadPreviewView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, upload_id):
        try:
            upload = _visible_upload_queryset(
                request.user
            ).get(pk=upload_id)

        except OCRUpload.DoesNotExist as exc:
            raise NotFound(
                "OCR upload not found."
            ) from exc

        if not upload.file:
            raise NotFound(
                "OCR file is not available."
            )

        try:
            file_handle = upload.file.open("rb")

        except Exception as exc:
            logger.exception(
                "Unable to open OCR preview — upload_id=%s",
                upload_id,
            )
            raise NotFound(
                "OCR file could not be opened."
            ) from exc

        response = FileResponse(
            file_handle,
            content_type=upload.mime_type
            or "application/octet-stream",
        )

        response["Content-Disposition"] = (
            f'inline; filename="{upload.original_filename}"'
        )

        return response


class OCRBatchStatusView(APIView):
    """
    GET /api/v1/ocr/extract/batches/<batch_id>/

    Returns batch progress and completed extraction results.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, batch_id):
        queryset = OCRBatch.objects.prefetch_related(
            "uploads__document__versions"
        )

        if _is_company_admin(request.user):
            queryset = queryset.filter(company=request.user.company)
        else:
            queryset = queryset.filter(
                user=request.user,
                company=request.user.company,
            )

        try:
            batch = queryset.get(pk=batch_id)
        except OCRBatch.DoesNotExist as exc:
            raise NotFound("OCR batch not found.") from exc

        uploads = list(batch.uploads.all().order_by("created_at"))

        completed = sum(
            1 for upload in uploads
            if upload.status == OCRUpload.Status.COMPLETED
        )
        failed = sum(
            1 for upload in uploads
            if upload.status == OCRUpload.Status.FAILED
        )
        processing = sum(
            1 for upload in uploads
            if upload.status == OCRUpload.Status.PROCESSING
        )
        queued = sum(
            1 for upload in uploads
            if upload.status == OCRUpload.Status.UPLOADED
        )

        # The task updates the batch status, but this defensive reconciliation
        # also corrects status if a worker dies between state transitions.
        total = len(uploads)

        if total and completed == total:
            batch_status = OCRBatch.Status.COMPLETED
        elif total and failed == total:
            batch_status = OCRBatch.Status.FAILED
        elif failed and completed + failed == total:
            batch_status = OCRBatch.Status.PARTIAL
        else:
            batch_status = (
                OCRBatch.Status.PROCESSING
                if total
                else OCRBatch.Status.FAILED
            )

        if batch.status != batch_status and batch_status in {
            OCRBatch.Status.COMPLETED,
            OCRBatch.Status.FAILED,
            OCRBatch.Status.PARTIAL,
        }:
            batch.status = batch_status
            batch.completed_at = timezone.now()
            batch.save(update_fields=["status", "completed_at"])

        results = []
        for upload in uploads:
            document = getattr(upload, "document", None)
            version = None

            if document is not None:
                version = document.versions.order_by(
                    "-version_number"
                ).first()
            live_data = _get_live_ocr_result(
                str(upload.id)
            )
            results.append(
                {
                    "status": upload.status,
                    "upload_id": str(upload.id),
                    "document_id": (
                        str(document.id) if document else None
                    ),
                    "version_id": str(version.id) if version else None,
                    "version_number": (
                        version.version_number if version else None
                    ),
                    "filename": upload.original_filename,
                    "preview_url": (
                        f"/ocr/extract/"
                        f"uploads/{upload.id}/preview/"
                    ),

                    "data": (
                        # _get_live_result(str(upload.id))
                        # if _get_live_result(str(upload.id)) is not None
                        live_data
                        if live_data is not None
                        else (
                            version.normalized_json
                            if version
                            else None
                        ),
                    ),

                    "error": (
                        upload.failure_reason
                        if upload.status == OCRUpload.Status.FAILED
                        else None
                    ),
                }
            )

        return Response(
            {
                "batch_id": str(batch.id),
                "status": batch_status,
                "source_type": batch.source_type,
                "source_filename": batch.original_filename,
                "total_files": total,
                "queued_files": queued,
                "processing_files": processing,
                "completed_files": completed,
                "failed_files": failed,
                "files": results,
                "requested_fields": batch.requested_fields_json or None,
                "created_at": batch.created_at,
                "started_at": batch.started_at,
                "completed_at": batch.completed_at,
            },
            status=status.HTTP_200_OK,
        )