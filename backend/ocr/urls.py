"""
URL configuration for the OCR application.

All OCR endpoints are mounted under /api/v1/ocr/ via the root
``config/urls.py`` include.
"""

from django.urls import path

from ocr.views import UploadView

urlpatterns = [
    path('upload/', UploadView.as_view(), name='ocr-upload'),
]