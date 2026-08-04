"""
URL configuration for the invoice application.

All invoice endpoints are mounted under /api/v1/invoice/ via the root
``config/urls.py`` include.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from invoice.views import (
    InvoiceUploadView,
    InvoiceBatchViewSet,
    InvoiceFileViewSet,
    InvoiceReviewView,
    InvoiceNetSuiteMappingViewSet,
    InvoicePayloadPreviewView,
)

router = DefaultRouter()
router.register(r'batches', InvoiceBatchViewSet, basename='invoice-batch')
router.register(r'files', InvoiceFileViewSet, basename='invoice-file')
router.register(r'netsuite-mapping', InvoiceNetSuiteMappingViewSet, basename='invoice-netsuite-mapping')

urlpatterns = [
    path('upload/', InvoiceUploadView.as_view(), name='invoice-upload'),
    path('review/<int:file_id>/', InvoiceReviewView.as_view(), name='invoice-review'),
    path('preview-payload/<int:file_id>/', InvoicePayloadPreviewView.as_view(), name='invoice-preview-payload'),
    path('', include(router.urls)),
]