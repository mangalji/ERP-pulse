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
    OCRExtractView,
    OCRBatchStatusView,
    OCRUploadPreviewView,   
)

urlpatterns = [
    path('upload/', UploadView.as_view(), name='ocr-upload'),
    path('history/', OCRHistoryListView.as_view(), name='ocr-history'),
    path("history/batches/<uuid:batch_id>/",OCRBatchHistoryView.as_view(),name="ocr-batch-history"),
    path('documents/<uuid:document_id>/history/',DocumentHistoryView.as_view(),name='ocr-document-history'),
    path('documents/<uuid:document_id>/history/<int:version>/',DocumentVersionView.as_view(),name='ocr-document-version'),
    path("extract/",OCRExtractView.as_view(),name="ocr-extract"),
    path("extract/uploads/<uuid:upload_id>/preview/",OCRUploadPreviewView.as_view(),name="ocr-upload-preview"),
    path("extract/batches/<uuid:batch_id>/",OCRBatchStatusView.as_view(),name="ocr-batch-status"),
    path("extraction-templates/",OCRExtractionTemplateListView.as_view(),name="ocr-extraction-templates"),
    path("extraction-templates/<uuid:template_id>/",OCRExtractionTemplateDetailView.as_view(),name="ocr-extraction-template-detail"),
    path("extraction-fields/",OCRStandardFieldsView.as_view(),name="ocr-extraction-fields"),
    path("review/save/",OCRReviewSaveView.as_view(),name="ocr-review-save"),
]
