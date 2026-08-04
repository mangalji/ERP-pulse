"""
API views for the OCR application.

Views are thin: they validate input via a serializer, delegate to
``OCRService``, and return the standard response envelope. No business
logic lives here.
"""

from __future__ import annotations

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from common.utils.response import success_response
from ocr.serializers import UploadSerializer, UploadResponseSerializer
from ocr.services import ocr_service
from ocr.utils import logger


class UploadView(APIView):
    """
    POST /api/v1/ocr/upload/

    Accepts an invoice file (PDF, PNG, JPG, JPEG, or WEBP; max 10 MB),
    validates it via ``UploadSerializer``, delegates storage to
    ``OCRService.upload()``, and returns the upload metadata.
    
    Authentication is required — only logged-in users can upload files.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = UploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        upload = ocr_service.upload(
            file = serializer.validated_data['file'],
            user=request.user,
        )
        response_serializer = UploadResponseSerializer(upload)
        return success_response(
            message='File uploaded successfully.',
            data=response_serializer.data,
            status_code=status.HTTP_201_CREATED,
        )