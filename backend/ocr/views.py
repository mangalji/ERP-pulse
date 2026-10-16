"""
API views for OCR uploads, history, validation state, and extraction templates.

Views validate requests and coordinate persistence and delegated OCR services.
"""

from __future__ import annotations

import json
import redis
import uuid

from django.conf import settings

from common.infra import get_redis_client, warn_throttled
from django.http import FileResponse
from django.db import transaction
from django.db.models import Prefetch
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from common.common_utils import success_response
from rest_framework.response import Response
from ocr.models import OCRDocument, OCRDocumentVersion, OCRUpload, OCRBatch, OCRExtractionTemplate, OCRValidationResult
from netsuite.models import NetSuiteOCRPosting
from netsuite.oauth import netsuite_vendor_bill_url
from ocr.serializers import (
    DocumentHistorySerializer,
    DocumentVersionSerializer,
    OCRBatchHistorySerializer,
    OCRHistoryEntrySerializer,
    OCRSaveRequestSerializer,
    OCRExtractionTemplateSerializer,
    OCRExtractionTemplateCreateSerializer,
    OCRExtractionTemplateUpdateSerializer,
)
from ocr.pdf_processor import get_fitz
from ocr.exceptions import OCRException
from ocr.services import ocr_service
from ocr.services.extraction_persistence import persist_extraction
from ocr.notebook_extraction_service import get_standard_field_catalog, resolve_field_config
from ocr.exceptions import OCRTimeBudgetExceeded
from ocr.execution import dispatch_upload, recover_batch
from ocr.tasks import process_single_ocr_upload
from ocr.utils import logger
from ocr.services.zip_upload_service import (
    ZipValidationError,
    extract_supported_files_from_zip,
)

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
    Resolve extraction configuration only from a saved company template.
    ``OCRBatch.requested_fields_json`` will snapshot this JSON for deterministic
    processing. Inline request mappings are deliberately unsupported so a
    caller cannot bypass template save-time validation.
    """
    template_id = request.data.get("template_id")
    if not template_id:
        raise ValueError(
            "A saved OCR extraction template is required. Select a template before uploading."
         )
    requested_fields = _resolve_template_config(
        template_id,
        request.user,
    )
    if not requested_fields:
        raise ValueError(
            "The selected OCR extraction template has no saved field configuration. Open and save the template before uploading."
        )

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
    """Read the unsaved AI extraction result from Redis, then DB fallback."""

    cache_key = f"erp-pulse:ocr:live:{upload_id}"
    try:
        client = get_redis_client()
        cached = client.get(cache_key)
        if cached:
            result = json.loads(cached)

            if isinstance(result,dict):
                return result

    except redis.RedisError as exc:
        warn_throttled(
            "ocr-live-result-redis-read",
            "Redis live OCR result unavailable; reading from PostgreSQL: %s",
            exc,
            )

    try:
        upload = OCRUpload.objects.only(
            "live_result_json",
            "live_result_expires_at",
        ).get(pk=upload_id)

        if (
            upload.live_result_json is not None
            and upload.live_result_expires_at
            and upload.live_result_expires_at > timezone.now()
        ):
            return upload.live_result_json

    except OCRUpload.DoesNotExist:
        return None
    
    except Exception:
        logger.exception(
            "Failed to read DB live OCR result — upload_id=%s",
            upload_id,
        )

    return None


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

    live_data = _get_live_ocr_result(str(upload.id))

    return {
        "upload_id": upload.id,
        "document_id": document.id if document else None,
        "version_id": version.id if version else None,
        "version_number": (
            version.version_number if version else None
        ),
        "filename": upload.original_filename,
        "status": upload.status,
        "data": live_data if live_data is not None else version.normalized_json if version else None,
        "error": (
            upload.failure_reason
            if upload.status == OCRUpload.Status.FAILED
            else None
        ),
    }


def _prepare_history_deletion(*, user, record_id, record_type):
    """Load one visible history record and its files before deleting it."""

    if record_type == "batch":
        try:
            batch = (
                _visible_batch_queryset(user)
                .prefetch_related("uploads__document__versions")
                .get(pk=record_id)
            )
        except OCRBatch.DoesNotExist as exc:
            raise NotFound("OCR history batch not found.") from exc

        uploads = list(batch.uploads.all())
        history_id = batch.id
    elif record_type == "upload":
        try:
            upload = (
                _visible_upload_queryset(user)
                .prefetch_related("document__versions")
                .get(pk=record_id)
            )
        except OCRUpload.DoesNotExist as exc:
            raise NotFound("OCR history file not found.") from exc

        uploads = [upload]
        batch = upload.batch
        history_id = upload.batch_id or upload.id
    else:
        raise ValueError("record_type must be 'upload' or 'batch'.")

    document_ids = [
        upload.document.id
        for upload in uploads
        if getattr(upload, "document", None) is not None
    ]
    if NetSuiteOCRPosting.objects.filter(
        document_id__in=document_ids,
        status="posted",
    ).exists():
        raise ValueError("Posted OCR history records cannot be deleted.")

    stored_files = []
    seen_files = set()

    def remember_file(field_file):
        if not field_file or not field_file.name:
            return

        file_key = (id(field_file.storage), field_file.name)
        if file_key not in seen_files:
            seen_files.add(file_key)
            stored_files.append((field_file.storage, field_file.name))

    for upload in uploads:
        remember_file(upload.file)
        document = getattr(upload, "document", None)
        if document is not None:
            for version in document.versions.all():
                remember_file(version.original_document)
                remember_file(version.processed_document)

    return {
        "record_id": record_id,
        "record_type": record_type,
        "history_id": history_id,
        "batch": batch,
        "uploads": uploads,
        "stored_files": stored_files,
    }


def _delete_prepared_history_record(deletion):
    """Delete one prepared history record inside the caller's transaction."""

    for upload in deletion["uploads"]:
        upload.delete()

    batch = deletion["batch"]
    if batch is not None:
        if deletion["record_type"] == "batch":
            batch.delete()
        elif not OCRUpload.objects.filter(batch_id=batch.id).exists():
            batch.delete()

    def remove_stored_files():
        for storage, name in deletion["stored_files"]:
            try:
                storage.delete(name)
            except Exception:
                logger.exception(
                    "Failed to remove stored OCR file after history deletion: %s",
                    name,
                )

    transaction.on_commit(remove_stored_files)

    return {
        "record_id": str(deletion["record_id"]),
        "record_type": deletion["record_type"],
        "history_id": str(deletion["history_id"]),
    }


class OCRHistoryUploadDeleteView(APIView):
    """Delete one OCR history file; only a company admin may do this."""

    permission_classes = [IsAuthenticated]

    def delete(self, request, upload_id):
        if not _is_company_admin(request.user):
            return Response(
                {"detail": "Only company admins can delete OCR history files."},
                status=status.HTTP_403_FORBIDDEN,
            )

        record_type = str(
            request.query_params.get("record_type", "upload")
        ).strip().lower()

        try:
            deletion = _prepare_history_deletion(
                user=request.user,
                record_id=upload_id,
                record_type=record_type,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            result = _delete_prepared_history_record(deletion)

        return success_response(
            message="OCR history record deleted successfully.",
            data=result,
        )


class OCRHistoryBulkDeleteView(APIView):
    """Synchronously delete selected OCR history records in one request."""

    permission_classes = [IsAuthenticated]

    def delete(self, request):
        if not _is_company_admin(request.user):
            return Response(
                {"detail": "Only company admins can delete OCR history files."},
                status=status.HTTP_403_FORBIDDEN,
            )

        records = request.data.get("records") if isinstance(request.data, dict) else None
        if not isinstance(records, list) or not records:
            return Response(
                {"detail": "records must be a non-empty list."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(records) > 100:
            return Response(
                {"detail": "A maximum of 100 history records can be deleted at once."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        targets = []
        seen_targets = set()
        try:
            for record in records:
                if not isinstance(record, dict):
                    raise ValueError("Each records entry must be an object.")

                record_id = uuid.UUID(str(record.get("id", "")))
                record_type = str(record.get("record_type", "")).strip().lower()
                target_key = (str(record_id), record_type)
                if target_key in seen_targets:
                    continue

                seen_targets.add(target_key)
                targets.append(
                    _prepare_history_deletion(
                        user=request.user,
                        record_id=record_id,
                        record_type=record_type,
                    )
                )
        except (TypeError, ValueError) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        selected_upload_ids = set()
        for target in targets:
            upload_ids = {upload.id for upload in target["uploads"]}
            if selected_upload_ids.intersection(upload_ids):
                return Response(
                    {"detail": "The same OCR file cannot be deleted more than once."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            selected_upload_ids.update(upload_ids)

        with transaction.atomic():
            deleted = [_delete_prepared_history_record(target) for target in targets]

        return success_response(
            message=f"{len(deleted)} OCR history record(s) deleted successfully.",
            data={"deleted": deleted, "count": len(deleted)},
        )


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

    Returns one top-level history record per single upload or per multiple-file
    OCR batch. Validation/posting state is derived from the latest version of
    every document in the record.
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
        # Everything the loops below need is loaded here in a fixed number of
        # queries. Calling .order_by()/.first() on a related manager later would
        # bypass the prefetch and run one extra query per batch / document.
        batches = list(
            _visible_batch_queryset(request.user)
            .select_related("user")
            .prefetch_related(              # .prefetch_related("uploads__document__versions")
                Prefetch(
                    "uploads",
                    queryset=(
                        OCRUpload.objects
                        .select_related("document")
                        .order_by("created_at")
                        ),
                        to_attr="ordered_uploads",
                    ),
                    # Only the latest version's id is needed here, so skip the
                    # large JSON columns (raw_ocr, normalized_json, ...).
                    Prefetch(
                        "ordered_uploads__document__versions",
                        queryset=(
                            OCRDocumentVersion.objects
                            .only("id","document_id","version_number")
                            .order_by("-version_number")
                        ),
                        to_attr="ordered_versions",
                    ),
                )
            .order_by("-created_at")
        )

        document_by_upload = {}
        version_by_document = {}
        all_document_ids = []
        all_version_ids = []

        for batch in batches:
            # for upload in batch.uploads.all().order_by("created_at"):
            for upload in batch.ordered_uploads:
                document = getattr(upload, "document", None)
                document_by_upload[upload.id] = document

                if document is None:
                    continue

                version = (
                    document.ordered_versions[0] if document.ordered_versions else None
                )
                version_by_document[document.id] = version
                all_document_ids.append(document.id)
                if version is not None:
                    all_version_ids.append(version.id)

        latest_validation = {}
        if all_document_ids:
            validations = (
                OCRValidationResult.objects
                .filter(document_id__in=all_document_ids)
                .order_by("document_id", "-created_at")
            )

            for validation in validations:
                document_id = validation.document_id
                current_version = version_by_document.get(document_id)
                if (
                    current_version is not None
                    and validation.version_id != current_version.id
                ):
                    continue
                if document_id not in latest_validation:
                    latest_validation[document_id] = validation

        latest_posting = {}
        if all_document_ids and all_version_ids:
            postings = (
                NetSuiteOCRPosting.objects
                .select_related("connection")
                .filter(
                    document_id__in=all_document_ids,
                    version_id__in=all_version_ids,
                )
                .order_by("document_id", "version_id", "-created_at")
            )

            for posting in postings:
                key = (posting.document_id, posting.version_id)
                if key not in latest_posting:
                    latest_posting[key] = posting

        results = []

        for batch in batches:
            uploads = batch.ordered_uploads
            if not uploads:
                continue

            is_multiple = (
                str(batch.processing_mode).upper()
                == OCRBatch.ProcessingMode.MULTIPLE
                or len(uploads) > 1
            )

            document_ids = [
                str(document_by_upload[upload.id].id)
                for upload in uploads
                if document_by_upload.get(upload.id) is not None
            ]

            validations = [
                latest_validation.get(document_by_upload[upload.id].id)
                for upload in uploads
                if document_by_upload.get(upload.id) is not None
            ]

            postings = [
                latest_posting.get(
                    (
                        document_by_upload[upload.id].id,
                        version_by_document[document_by_upload[upload.id].id].id,
                    )
                )
                for upload in uploads
                if (
                    document_by_upload.get(upload.id) is not None
                    and version_by_document.get(document_by_upload[upload.id].id)
                    is not None
                )
            ]

            total_documents = len(uploads)
            validated_count = sum(
                1
                for validation in validations
                if validation is not None
                and validation.status == "VALIDATED"
            )
            posted_count = sum(
                1
                for posting in postings
                if posting is not None
                and posting.status == "posted"
                and posting.netsuite_record_id
            )

            if posted_count == total_documents and total_documents:
                record_status = "POSTED"
            elif validated_count == total_documents and total_documents:
                record_status = "VALIDATED"
            else:
                record_status = "NOT_VALIDATED"

            validation_errors = []
            validation_ids = []
            validation_dates = []
            for validation in validations:
                if validation is None:
                    continue
                if validation.errors:
                    validation_errors.extend(validation.errors)
                validation_ids.append(str(validation.id))
                validation_dates.append(validation.created_at)

            netsuite_records = [
                {
                    "document_id": str(posting.document_id),
                    "internal_id": posting.netsuite_record_id,
                    "url": netsuite_vendor_bill_url(
                        account_id=posting.connection.netsuite_account_id,
                        record_id=posting.netsuite_record_id,
                    ),
                }
                for posting in postings
                if (
                    posting is not None
                    and posting.status == "posted"
                    and posting.netsuite_record_id
                )
            ]

            if is_multiple:
                filename = f"Batch — {total_documents} files"
                record_type = "batch"
                single_document_id = None
                single_upload_id = None
            else:
                first_upload = uploads[0]
                filename = first_upload.original_filename
                record_type = "single"
                first_document = document_by_upload.get(first_upload.id)
                single_document_id = (
                    str(first_document.id)
                    if first_document is not None
                    else None
                )
                single_upload_id = str(first_upload.id)

            results.append(
                {
                    "type": record_type,
                    "batch_id": str(batch.id),
                    "history_number": batch.history_number,
                    "document_id": single_document_id,
                    "document_ids": document_ids,
                    "upload_id": single_upload_id,
                    "filename": filename,
                    "file_count": total_documents,
                    "status": batch.status,
                    "source_type": batch.source_type,
                    "created_at": batch.created_at,
                    "owner_id": str(batch.user_id),
                    "owner_name": _user_display_name(batch.user),
                    "validation_status": record_status,
                    "validation_errors": validation_errors,
                    "validation_id": validation_ids[-1] if validation_ids else None,
                    "validation_updated_at": max(validation_dates) if validation_dates else None,
                    "validated_count": validated_count,
                    "posted_count": posted_count,
                    "netsuite_records": netsuite_records,
                }
            )

        status_filter = str(request.query_params.get("status", "")).strip().upper()
        if status_filter in {"NOT_VALIDATED", "VALIDATED", "POSTED"}:
            results = [
                item
                for item in results
                if item["validation_status"] == status_filter
            ]

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
        latest_version = versions[-1] if versions else None

        validation_payload = None
        posting_payload = None
        if latest_version is not None:
            validation = (
                OCRValidationResult.objects.filter(
                    document=document,
                    version=latest_version,
                )
                .order_by("-created_at")
                .first()
            )
            if validation is not None:
                items = validation.items if isinstance(validation.items, list) else []
                matched_rows = sum(1 for item in items if item.get("matched"))
                unique_netsuite_items = {
                    str(item.get("netsuite_id"))
                    for item in items
                    if item.get("netsuite_id") not in (None, "")
                }
                validation_payload = {
                    "validation_id": str(validation.id),
                    "status": validation.status,
                    "vendor": {
                        "extracted_name": validation.vendor_extracted_name,
                        "matched": validation.vendor_matched,
                        "netsuite_id": validation.vendor_netsuite_id,
                    },
                    "items": items,
                    "errors": validation.errors,
                    "ai_diagnostics": validation.ai_diagnostics,
                    "summary": {
                        "source_rows": len(items),
                        "matched_rows": matched_rows,
                        "unique_netsuite_items": len(unique_netsuite_items),
                        "unmatched_rows": len(items) - matched_rows,
                    },
                }

            posting = (
                NetSuiteOCRPosting.objects.select_related("connection")
                .filter(document=document, version=latest_version)
                .first()
            )
            if posting is not None:
                record_url = None
                if posting.status == "posted" and posting.netsuite_record_id:
                    record_url = netsuite_vendor_bill_url(
                        account_id=posting.connection.netsuite_account_id,
                        record_id=posting.netsuite_record_id,
                    )
                posting_payload = {
                    "status": posting.status,
                    "netsuite_record_id": posting.netsuite_record_id,
                    "netsuite_record_url": record_url,
                    "error_message": posting.error_message,
                }
        serializer = DocumentHistorySerializer(
            {
                "id": document.id,
                "document_type": document.document_type,
                "status": document.status,
                "upload_id": document.upload_id,
                "filename": (getattr(document.upload, "original_filename",None) if document.upload_id else None),
                "current_version": document.current_version,
                "overall_confidence": document.overall_confidence,
                "processing_metadata": document.processing_metadata,
                "requested_fields": (
                    getattr(getattr(document.upload, 'batch', None), 'requested_fields_json', None)
                    if document.upload_id
                    else None
                ),
                "validation": validation_payload,
                "posting": posting_payload,
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
                {"detail": "Unable to save OCR result."},
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
                "data": version.reviewed_json,
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
                "data": version.reviewed_json,
            },
            status_code=status.HTTP_200_OK,
        )

class OCRExtractionTemplateListView(APIView):
    """List/create company-scoped dynamic OCR extraction templates."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = OCRExtractionTemplate.objects.filter(
            company=request.user.company
        
        ).order_by("created_at","id")
        serializer = OCRExtractionTemplateSerializer(queryset, many=True, context={"request":request},)
        return success_response(
            message="Extraction templates fetched successfully.",
            data=serializer.data,
        )

    def post(self, request):
        serializer = OCRExtractionTemplateCreateSerializer(
            data=request.data, context={"request": request}
        )
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
            data=OCRExtractionTemplateSerializer(template,context={"request":request}).data,
            status_code=status.HTTP_201_CREATED,
        )

class OCRExtractionTemplateDetailView(APIView):
    """Retrieve, partially update, or delete a company-scoped extraction template."""

    permission_classes = [IsAuthenticated]

    def _get_template(self, request, template_id):
        try:
            return OCRExtractionTemplate.objects.get(
                pk=template_id,
                company=request.user.company,
            )
        except (
            OCRExtractionTemplate.DoesNotExist,
            ValueError,
            TypeError,
        ):
            raise NotFound("Extraction template not found.")

    def get(self, request, template_id):
        template = self._get_template(request, template_id)

        return success_response(
            message="Extraction template fetched successfully.",
            data=OCRExtractionTemplateSerializer(template,context={"request": request}).data,
        )

    def patch(self, request, template_id):
        template = self._get_template(request, template_id)

        serializer = OCRExtractionTemplateUpdateSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)

        validated_data = serializer.validated_data

        is_preferred = validated_data.pop(
            "is_preferred",
            None,
        )

        if "name" in validated_data:
            new_name = validated_data["name"]

            duplicate_exists = (
                OCRExtractionTemplate.objects
                .filter(
                    company=request.user.company,
                    name=new_name,
                )
                .exclude(pk=template.pk)
                .exists()
            )

            if duplicate_exists:
                return Response(
                    {
                        "detail": (
                            "An extraction template with this name "
                            "already exists."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            template.name = new_name

        if "fields_config" in validated_data:
            template.fields_config = validated_data["fields_config"]

        template.save(
            update_fields=[
                field
                for field in ("name", "fields_config")
                if field in validated_data
            ]
            + ["updated_at"]
        )
        if is_preferred is True:
            request.user.preferred_ocr_template = template
            request.user.save(
                update_fields=["preferred_ocr_template"]
            )
        
        elif is_preferred is False:
            if request.user.preferred_ocr_template_id == template.id:
                request.user.preferred_ocr_template = None
                request.user.save(
                    update_fields=["preferred_ocr_template"]
                )

        return success_response(
            message="Extraction template updated successfully.",
            data=OCRExtractionTemplateSerializer(template,context={"request": request}).data,
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
    Accept OCR uploads in Single or Multiple mode.

    Single mode processes one supported file synchronously without Celery.

    Multiple mode accepts up to the configured file limit and queues
    each file through the existing Celery processing pipeline.
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
            except OCRException:
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
    def _serialize_upload(upload):
        version = None

        document = getattr(upload, "document", None)
        if document is not None:
            version = document.versions.order_by("-version_number").first()

        live_data = _get_live_ocr_result(str(upload.id))
        item = {
            "status": upload.status,
            "upload_id": str(upload.id),
            "document_id": str(document.id) if document else None,
            "version_id": str(version.id) if version else None,
            "version_number": version.version_number if version else None,
            "filename": upload.original_filename,
            "error": upload.failure_reason if upload.status == OCRUpload.Status.FAILED else None,
            "data": live_data if live_data is not None else version.normalized_json if version else None,
        }

        return item

    def _accept_for_background(self, request, batch, created_uploads):
        """
        Hand every upload to the best available background executor
        (Celery -> in-process threads -> inline) and answer 202; the client
        polls the batch status. Executor failures fall back automatically.
        """
        modes = set()

        for upload in created_uploads:
            modes.add(
                dispatch_upload(str(upload.id), str(request.user.id))
            )

        return Response(
            {
                "batch_id": str(batch.id),
                "status": batch.status,
                "source_type": batch.source_type,
                "source_filename": batch.original_filename,
                "total_files": len(created_uploads),
                "queued_files": len(created_uploads),
                "execution_mode": (
                    next(iter(modes)) if len(modes) == 1 else "mixed"
                ),
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


    def post(self, request):

        mode = str(
            request.data.get("mode", "multiple")
        ).strip().lower()
        if mode not in {"single", "multiple"}:
            return Response(
                {
                    "detail":"Invalid OCR mode, Use 'single' or 'multiple'."
                },status=status.HTTP_400_BAD_REQUEST,
            )
        if mode == "multiple" and not settings.OCR_MULTIPLE_ENABLED:
            return Response(
                {
                    "detail": (
                        "Multiple OCR processing is currently unavailable. "
                        "Please use Single mode."
                    )
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
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

        if mode == "single" and len(uploaded_files) != 1:
            return Response(
                {
                    "detail": (
                        "Single mode accepts exactly one file."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if mode == "single" and self._is_zip(uploaded_files[0]):
            return Response(
                {
                    "detail": (
                        "ZIP archives are not supported in Single mode."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if (
            mode == "multiple"
            and len(uploaded_files) > settings.OCR_MULTI_MAX_FILES
        ):
            return Response(
                {
                    "detail": (
                        f"Multiple mode supports a maximum of "
                        f"{settings.OCR_MULTI_MAX_FILES} files."
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

            if mode == "single":
                single_file = actual_files[0]
                filename = (getattr(single_file, "name", "") or "").lower()
                content_type = (
                    getattr(single_file, "content_type", "") or ""
                ).lower()

                is_pdf = (
                    filename.endswith(".pdf")
                    or content_type == "application/pdf"
                )
                if is_pdf:
                    try:
                        single_file.seek(0)
                        fitz = get_fitz()
                        pdf_doc = fitz.open(
                            stream = single_file.read(), filetype="pdf"
                        )
                        page_count = pdf_doc.page_count
                        pdf_doc.close()
                        single_file.seek(0)
                    except Exception:
                        logger.exception(
                            "Unable to inspect Single OCR PDF — filename=%s",
                            filename,
                        )
                        return Response(
                            {
                                "detail": "The uploaded PDF could not be read. "
                                "Please upload a valid PDF."
                            },
                            status=status.HTTP_400_BAD_REQUEST,
                        )

                    if page_count > settings.OCR_SINGLE_MAX_PAGES:
                        return Response(
                            {
                                "detail": (
                                    f"Single mode supports a maximum of "
                                    f"{settings.OCR_SINGLE_MAX_PAGES} PDF pages. "
                                    f"The uploaded PDF contains {page_count} pages."
                                ),
                                "page_count": page_count,
                                "max_pages": settings.OCR_SINGLE_MAX_PAGES,
                            },
                            status=status.HTTP_400_BAD_REQUEST,
                        )
                    
            if (
                mode == "multiple"
                and len(actual_files) > settings.OCR_MULTI_MAX_FILES
            ):
                raise ZipValidationError(
                    f"Multiple mode supports a maximum of "
                    f"{settings.OCR_MULTI_MAX_FILES} files."
                )

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
                processing_mode = (
                    OCRBatch.ProcessingMode.SINGLE
                    if mode == "single"
                    else OCRBatch.ProcessingMode.MULTIPLE
            ),
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
            if mode == "single":
                upload = created_uploads[0]

                # Hosts with short request limits can ask for pure
                # accept-and-poll behaviour.
                if getattr(settings, "OCR_SINGLE_ASYNC", False):
                    return self._accept_for_background(
                        request, batch, created_uploads
                    )

                try:
                    process_single_ocr_upload(
                        upload_id=str(upload.id),
                        user_id=str(request.user.id),
                        time_budget_seconds=(
                            settings.OCR_SINGLE_TIME_BUDGET_SECONDS
                        ),
                        handoff_on_budget=True,
                    )
                except OCRTimeBudgetExceeded:
                    # Not a failure: the file is processed in the background
                    # and the client polls the batch status.
                    return self._accept_for_background(
                        request, batch, created_uploads
                    )
                
                except Exception as exc:
                    logger.warning(
                        "Single OCR processing failed — "
                        "upload_id=%s batch_id=%s reason=%s",
                        upload.id,
                        batch.id,
                        exc,
                    )

                    upload.refresh_from_db()

                    if upload.status != OCRUpload.Status.FAILED:
                        upload.status = OCRUpload.Status.FAILED
                        upload.failure_reason = (
                            "Single OCR processing failed."
                        )
                        upload.save(
                            update_fields=[
                                "status",
                                "failure_reason",
                            ]
                        )

                    batch.status = OCRBatch.Status.FAILED
                    batch.completed_at = timezone.now()
                    batch.save(
                        update_fields=[
                            "status",
                            "completed_at",
                        ]
                    )

                    return Response(
                        {
                            "batch_id": str(batch.id),
                            "status": batch.status,
                            "total_files": 1,
                            "queued_files": 0,
                            "files": [
                                self._serialize_upload(upload)
                            ],
                        },
                        status=status.HTTP_200_OK,
                    )

                upload.refresh_from_db()
                batch.refresh_from_db()

                return Response(
                    {
                        "batch_id": str(batch.id),
                        "status": batch.status,
                        "source_type": batch.source_type,
                        "source_filename": batch.original_filename,
                        "total_files": 1,
                        "queued_files": 0,
                        "files": [
                            self._serialize_upload(upload)
                        ],
                    },
                    status=status.HTTP_200_OK,
                )

            # MULTIPLE MODE
            return self._accept_for_background(
                request, batch, created_uploads
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
                    "detail": "OCR batch submission failed. Please try again.",
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

        except FileNotFoundError:
            # The upload record may outlive the underlying file. This can
            # happen with a local MEDIA_ROOT reset or a missing DB-storage row.
            # Treat it as an expected missing-preview condition, not an
            # unhandled storage exception. Keep the saved OCR result intact.
            logger.warning(
                "OCR preview source file is missing from storage — "
                "upload_id=%s storage_name=%s",
                upload_id,
                upload.file.name,
            )
            return Response(
                {
                    "detail": (
                        "The original uploaded file is no longer available in "
                        "storage, so its preview cannot be displayed. Your "
                        "saved OCR result is still available. Re-upload the "
                        "source file if you need to view it again."
                    )
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        except Exception as exc:
            logger.exception(
                "Unable to open OCR preview — upload_id=%s",
                upload_id,
            )
            return Response(
                {
                    "detail": (
                        "The original file preview could not be loaded because "
                        "of a storage error. Your saved OCR result is still "
                        "available. Please try again later."
                    )
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

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

        # Self-healing: re-queue jobs whose worker died or that were never
        # picked up. Triggered by the client's polling, so it needs no
        # scheduler. A failure here must never break the status response.
        try:
            if recover_batch(batch.id):
                batch = queryset.get(pk=batch_id)
        except Exception as exc:  # noqa: BLE001
            warn_throttled(
                "ocr-recovery-failed",
                "OCR job recovery skipped: %s",
                exc,
            )

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


class OCRUploadModesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(
            {
                "single": {
                    "enabled": True,
                    "max_files": 1,
                    "max_pdf_pages": settings.OCR_SINGLE_MAX_PAGES,
                    "time_budget_seconds": (
                        settings.OCR_SINGLE_TIME_BUDGET_SECONDS
                    ),
                },
                "multiple": {
                    "enabled": settings.OCR_MULTIPLE_ENABLED,
                    "max_files": settings.OCR_MULTI_MAX_FILES,
                },
            },
            status=status.HTTP_200_OK,
        )
