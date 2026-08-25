"""
URL configuration for the OCR application.

All OCR endpoints are mounted under /api/v1/ocr/ via the root
``config/urls.py`` include.
"""

from django.urls import path

from ocr.views import (
    DocumentHistoryView,
    DocumentVersionView,
    OCRHistoryListView,
    OCRBatchHistoryView,
    UploadView,
    OCRReviewSaveView,
    OCRExtractionTemplateListView,
    OCRExtractionTemplateDetailView,
    OCRStandardFieldsView,
)
from .test_ocr_view import OCRTestExtractView, OCRTestBatchStatusView, OCRTestUploadPreviewView

urlpatterns = [
    path('upload/', UploadView.as_view(), name='ocr-upload'),
    path('history/', OCRHistoryListView.as_view(), name='ocr-history'),
    path("history/batches/<uuid:batch_id>/",OCRBatchHistoryView.as_view(),name="ocr-batch-history"),
    path('documents/<uuid:document_id>/history/',DocumentHistoryView.as_view(),name='ocr-document-history'),
    path('documents/<uuid:document_id>/history/<int:version>/',DocumentVersionView.as_view(),name='ocr-document-version'),
    path("test-extract/",OCRTestExtractView.as_view(),name="ocr-test"),
    path("test-extract/uploads/<uuid:upload_id>/preview/",OCRTestUploadPreviewView.as_view(),name="ocr-test-upload-preview"),
    path("test-extract/batches/<uuid:batch_id>/",OCRTestBatchStatusView.as_view(),name="ocr-test-batch-status"),
    path("extraction-templates/",OCRExtractionTemplateListView.as_view(),name="ocr-extraction-templates"),
    path("extraction-templates/<uuid:template_id>/",OCRExtractionTemplateDetailView.as_view(),name="ocr-extraction-template-detail"),
    path("extraction-fields/",OCRStandardFieldsView.as_view(),name="ocr-extraction-fields"),
    path("review/save/",OCRReviewSaveView.as_view(),name="ocr-review-save"),
]
