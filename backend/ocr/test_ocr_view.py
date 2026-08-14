"""OCR test endpoint for asynchronous, rate-limited batch processing."""

from __future__ import annotations

import json

import redis
from django.conf import settings
from django.http import FileResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ocr.models import OCRBatch, OCRDocumentVersion, OCRUpload
from ocr.services.ocr_service import ocr_service
from ocr.services.zip_upload_service import (
    ZipValidationError,
    extract_supported_files_from_zip,
)
from ocr.tasks import process_test_ocr_upload_task
from ocr.utils import logger

def _live_result_key(upload_id: str) -> str:
    return f"erp-pulse:ocr:live:{upload_id}"


def _get_live_result(upload_id):
    try:
        client = redis.Redis.from_url(
            settings.CELERY_BROKER_URL,
            decode_responses=True,
        )

        cached = client.get(
            _live_result_key(upload_id)
        )

        return json.loads(cached) if cached else None

    except Exception:
        logger.exception(
            "Failed to read OCR live result — upload_id=%s",
            upload_id,
        )
        return None


def _visible_upload_queryset(user):
    queryset = OCRUpload.objects.select_related(
        "user",
        "batch",
        "document",
    )

    if (
        getattr(user, "is_superuser", False)
        or getattr(user, "is_staff", False)
        or user.user_roles.filter(
            role__name__iexact="Company Admin"
        ).exists()
    ):
        return queryset.filter(
            user__company_id=user.company_id,
        )

    return queryset.filter(
        user=user,
        user__company_id=user.company_id,
    )

class OCRTestExtractView(APIView):
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

        return user.user_roles.filter(
            role__name__iexact="Company Admin"
        ).exists()

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

            batch = OCRBatch.objects.create(
                user=request.user,
                company=company,
                source_type=source_type,
                original_filename=original_filename,
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
                upload.status = OCRUpload.Status.UPLOADED
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
                task = getattr(process_test_ocr_upload_task, "delay", None)

                if task is None:
                    # Development fallback if Celery is unavailable.
                    process_test_ocr_upload_task(
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



class OCRTestUploadPreviewView(APIView):
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


class OCRTestBatchStatusView(APIView):
    """
    GET /api/v1/ocr/test-extract/batches/<batch_id>/

    Returns batch progress and completed extraction results.
    """

    permission_classes = [IsAuthenticated]

    @staticmethod
    def _is_company_admin(user):
        if getattr(user, "is_superuser", False):
            return True

        if not getattr(user, "company_id", None):
            return False

        if getattr(user, "is_staff", False):
            return True

        return user.user_roles.filter(
            role__name__iexact="Company Admin"
        ).exists()

    def get(self, request, batch_id):
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
            live_data = _get_live_result(
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
                        f"/ocr/test-extract/"
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
                "created_at": batch.created_at,
                "started_at": batch.started_at,
                "completed_at": batch.completed_at,
            },
            status=status.HTTP_200_OK,
        )
