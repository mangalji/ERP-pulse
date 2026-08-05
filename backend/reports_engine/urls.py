from django.urls import include, path
from rest_framework.routers import DefaultRouter

from reports_engine.views import (
    ReportEmailView,
    ReportGenerateView,
    ReportHistoryViewSet,
    ReportPreviewView,
    ReportTemplateViewSet,
    ScheduledReportViewSet,
)

router = DefaultRouter()
router.register(r'templates', ReportTemplateViewSet, basename='reports-engine-template')
router.register(r'schedules', ScheduledReportViewSet, basename='reports-engine-schedule')
router.register(r'history', ReportHistoryViewSet, basename='reports-engine-history')

urlpatterns = [
    path('', include(router.urls)),
    path('generate/', ReportGenerateView.as_view(), name='reports-engine-generate'),
    path('preview/', ReportPreviewView.as_view(), name='reports-engine-preview'),
    path('email/', ReportEmailView.as_view(), name='reports-engine-email'),
]
