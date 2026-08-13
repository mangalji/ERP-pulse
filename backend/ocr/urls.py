"""
URL configuration for the OCR application.

All OCR endpoints are mounted under /api/v1/ocr/ via the root
``config/urls.py`` include.
"""

from django.urls import path

from ocr.views import (
    DocumentHistoryView,
    DocumentVersionView,
    UploadView,
)
from .test_ocr_view import OCRTestExtractView

urlpatterns = [
    path('upload/', UploadView.as_view(), name='ocr-upload'),
    path('documents/<uuid:document_id>/history/',DocumentHistoryView.as_view(),name='ocr-document-history'),
    path('documents/<uuid:document_id>/history/<int:version>/',DocumentVersionView.as_view(),name='ocr-document-version'),
    path("test-extract/",OCRTestExtractView.as_view(),name="ocr-test"),
]
