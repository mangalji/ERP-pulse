"""Isolated OCR test endpoint using the approved notebook extraction logic."""

from __future__ import annotations

from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ocr.services.ocr_service import ocr_service
from ocr.notebook_extraction_service import notebook_gemini_extractor
from ocr.services.extraction_persistence import persist_extraction
from ocr.utils import logger


class OCRTestExtractView(APIView):
    """Temporary synchronous extraction endpoint for controlled OCR testing."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        uploaded_file = request.FILES.get("file")

        if uploaded_file is None:
            return Response(
                {"detail": "No file uploaded. Please provide a file."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        upload = None

        try:
            # Reuse the existing, hardened upload/storage path.
            upload = ocr_service.upload(
                file=uploaded_file,
                user=request.user,
            )

            upload.status = upload.Status.PROCESSING
            upload.processing_started_at = timezone.now()
            upload.failure_reason = None
            upload.save(update_fields=["status", "processing_started_at", "failure_reason"])

            result = notebook_gemini_extractor.extract(
                file_path=upload.file.path,
                mime_type=upload.mime_type,
            )

            upload.status = upload.Status.COMPLETED
            upload.processing_completed_at = timezone.now()
            upload.processing_duration_ms = int(
                (upload.processing_completed_at - upload.processing_started_at).total_seconds()
                * 1000
            )
            upload.save(
                update_fields=[
                    "status",
                    "processing_completed_at",
                    "processing_duration_ms",
                ]
            )

            document, version = persist_extraction(
                upload=upload,
                user=request.user,
                result=result,
            )

            return Response(
                {
                    "status": "COMPLETED",
                    "upload_id": str(upload.id),
                    "document_id": str(document.id),
                    "version_id": str(version.id),
                    "version_number": version.version_number,
                    "filename": upload.original_filename,
                    "data": result,
                },
                status=status.HTTP_200_OK,
            )

        except Exception as exc:
            logger.exception(
                "Standalone OCR test extraction failed — upload_id=%s error=%s",
                getattr(upload, "id", None),
                exc,
            )

            if upload is not None:
                upload.status = upload.Status.FAILED
                upload.processing_completed_at = timezone.now()
                upload.failure_reason = str(exc)[:5000]
                update_fields = [
                    "status",
                    "processing_completed_at",
                    "failure_reason",
                ]
                if upload.processing_started_at:
                    upload.processing_duration_ms = int(
                        (
                            upload.processing_completed_at
                            - upload.processing_started_at
                        ).total_seconds()
                        * 1000
                    )
                    update_fields.append("processing_duration_ms")
                upload.save(update_fields=update_fields)

            return Response(
                {
                    "detail": "OCR extraction failed.",
                    "error": str(exc),
                    "upload_id": str(upload.id) if upload else None,
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
