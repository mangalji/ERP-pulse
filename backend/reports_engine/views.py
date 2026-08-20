"""
Reports Engine API views.

Thin views: authenticate the user, validate input, delegate to services
or Celery tasks, and return the standard success envelope. Business
logic lives in reports_engine/services and reports_engine/tasks.
"""

import time

from django.http import FileResponse
from django.shortcuts import get_object_or_404
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from audit.models import AuditAction
from audit.services import audit_service
from common.utils.pagination import paginated_response
from common.utils.response import success_response
from reports_engine.models import (
    ReportHistory,
    ReportStatus,
    ReportTemplate,
    ScheduledReport,
)
from reports_engine.serializers import (
    ReportHistorySerializer,
    ReportTemplateSerializer,
    ScheduledReportSerializer,
)
from reports_engine.services.export_service import ExportService
from reports_engine.services.report_service import (
    ReportFactory,
    generate_report_data,
)
from reports_engine.services.schedule_service import ScheduleService
from reports_engine.tasks import generate_report_task, send_report_email_task


def _audit(request, *, action, entity, entity_id=None, new_value=None, company=None):
    """Convenience wrapper for audit logging all reports-engine actions."""
    audit_service.log(
        module='reports',
        action=action,
        entity=entity,
        entity_id=str(entity_id) if entity_id else entity_id,
        company=company or getattr(request.user, 'company', None),
        user=request.user,
        new_value=new_value,
        ip_address=request.META.get('REMOTE_ADDR'),
    )


class ReportTemplateViewSet(viewsets.ModelViewSet):
    """CRUD for saved report templates. Company-scoped."""

    serializer_class = ReportTemplateSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'report_type']
    ordering_fields = ['name', 'report_type', 'updated_at']
    ordering = ['-updated_at']

    def get_queryset(self):
        return ReportTemplate.objects.filter(company=self.request.user.company)

    def perform_create(self, serializer):
        template = serializer.save(company=self.request.user.company, created_by=self.request.user)
        _audit(self.request, action=AuditAction.CREATE, entity='ReportTemplate', entity_id=template.id, new_value={'name': template.name})

    def perform_update(self, serializer):
        template = serializer.save()
        _audit(self.request, action=AuditAction.UPDATE, entity='ReportTemplate', entity_id=template.id, new_value={'name': template.name})

    def perform_destroy(self, instance):
        _audit(self.request, action=AuditAction.DELETE, entity='ReportTemplate', entity_id=instance.id)
        instance.delete()

    @action(detail=False, methods=['get'])
    def types(self, request):
        return success_response(
            message='Supported report types fetched.',
            data=ReportFactory.supported_types(),
        )


class ScheduledReportViewSet(viewsets.ModelViewSet):
    """CRUD for scheduled reports. Company-scoped."""

    serializer_class = ScheduledReportSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'report_type']
    ordering = ['-created_at']

    def get_queryset(self):
        return ScheduledReport.objects.filter(company=self.request.user.company)

    def perform_create(self, serializer):
        schedule = serializer.save(company=self.request.user.company, created_by=self.request.user)
        ScheduleService().activate(schedule=schedule)
        _audit(self.request, action=AuditAction.CREATE, entity='ScheduledReport', entity_id=schedule.id, new_value={'name': schedule.name, 'frequency': schedule.frequency})

    def perform_update(self, serializer):
        schedule = serializer.save()
        schedule.next_run_at = ScheduleService().compute_next_run(schedule=schedule)
        schedule.save(update_fields=['next_run_at', 'updated_at'])
        _audit(self.request, action=AuditAction.UPDATE, entity='ScheduledReport', entity_id=schedule.id, new_value={'name': schedule.name})

    def perform_destroy(self, instance):
        _audit(self.request, action=AuditAction.DELETE, entity='ScheduledReport', entity_id=instance.id)
        instance.delete()

    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        schedule = self.get_object()
        ScheduleService().activate(schedule=schedule)
        _audit(request, action=AuditAction.UPDATE, entity='ScheduledReport', entity_id=schedule.id, new_value={'is_active': True})
        return success_response(message='Schedule activated.', data=ScheduledReportSerializer(schedule).data)

    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        schedule = self.get_object()
        ScheduleService().deactivate(schedule=schedule)
        _audit(request, action=AuditAction.UPDATE, entity='ScheduledReport', entity_id=schedule.id, new_value={'is_active': False})
        return success_response(message='Schedule deactivated.', data=ScheduledReportSerializer(schedule).data)

    @action(detail=True, methods=['post'])
    def run_now(self, request, pk=None):
        from reports_engine.tasks import scheduled_report_task
        schedule = self.get_object()
        result = scheduled_report_task.delay(schedule_id=str(schedule.id))
        _audit(request, action=AuditAction.UPDATE, entity='ScheduledReport', entity_id=schedule.id, new_value={'run_now': True})
        return success_response(message='Scheduled report dispatched.', data={'task_id': result.id, 'id': str(schedule.id)})


class ReportGenerateView(APIView):
    """POST /reports/generate/ — create a ReportHistory and dispatch Celery."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        report_type = request.data.get('report_type')
        fmt = request.data.get('format', 'CSV').upper()
        filters = {
            'preset': request.data.get('preset'),
            'start_date': request.data.get('start_date'),
            'end_date': request.data.get('end_date'),
        }
        if not report_type:
            return Response({'detail': 'report_type is required.'}, status=status.HTTP_400_BAD_REQUEST)
        if fmt not in ['PDF', 'XLSX', 'CSV', 'JSON']:
            return Response({'detail': 'format must be PDF, XLSX, CSV or JSON.'}, status=status.HTTP_400_BAD_REQUEST)

        history = ReportHistory.objects.create(
            company=request.user.company,
            created_by=request.user,
            report_type=report_type,
            format=fmt,
            status=ReportStatus.PENDING,
            filters=filters,
        )
        _audit(request, action=AuditAction.CREATE, entity='ReportHistory', entity_id=history.id, new_value={'report_type': report_type, 'format': fmt})
        result = generate_report_task.delay(history_id=str(history.id))
        return success_response(
            message='Report generation started.',
            data={'id': str(history.id), 'task_id': result.id, 'status': history.status},
            status_code=status.HTTP_202_ACCEPTED,
        )


class ReportPreviewView(APIView):
    """POST /reports/preview/ — preview report data without saving."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        report_type = request.data.get('report_type')
        filters = {
            'preset': request.data.get('preset'),
            'start_date': request.data.get('start_date'),
            'end_date': request.data.get('end_date'),
        }
        if not report_type:
            return Response({'detail': 'report_type is required.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            payload = generate_report_data(report_type=report_type, user=request.user, **filters)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        # Estimate file size without writing: render to CSV in memory.
        try:
            data, _mime, _ext = ExportService().export(payload=payload, fmt='CSV')
            est_size = len(data)
        except Exception:
            est_size = 0

        _audit(request, action=AuditAction.EXPORT, entity='ReportPreview', new_value={'report_type': report_type, 'rows': len(payload.get('rows', []))})
        return success_response(
            message='Report preview generated.',
            data={
                'report_type': report_type,
                'summary': payload.get('summary', {}),
                'headers': payload.get('headers', []),
                'rows': payload.get('rows', [])[:50],
                'row_count': len(payload.get('rows', [])),
                'estimated_file_size': est_size,
            },
        )


class ReportHistoryViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only list + detail for report history."""

    serializer_class = ReportHistorySerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['report_type', 'status', 'format']
    ordering_fields = ['generated_at', 'status']
    ordering = ['-generated_at']

    def get_queryset(self):
        return ReportHistory.objects.filter(company=self.request.user.company)

    @action(detail=True, methods=['get'])
    def metadata(self, request, pk=None):
        history = self.get_object()
        _audit(request, action=AuditAction.VIEW, entity='ReportHistory', entity_id=history.id)
        return success_response(
            message='Report metadata fetched.',
            data={
                'id': str(history.id),
                'report_type': history.report_type,
                'format': history.format,
                'status': history.status,
                'record_count': history.record_count,
                'file_size': history.file_size,
                'execution_time_ms': history.execution_time_ms,
                'download_count': history.download_count,
                'generated_at': history.generated_at.isoformat(),
                'created_by': history.created_by.email if history.created_by else None,
            },
        )

    @action(detail=True, methods=['get'])
    def download(self, request, pk=None):
        history = self.get_object()
        if history.status != ReportStatus.COMPLETED or not history.file:
            return Response({'detail': 'Report file not available.'}, status=status.HTTP_400_BAD_REQUEST)
        history.download_count += 1
        history.save(update_fields=['download_count'])
        _audit(request, action=AuditAction.EXPORT, entity='ReportHistory', entity_id=history.id, new_value={'download': True})
        return FileResponse(history.file.open('rb'), as_attachment=True, filename=history.file.name.rsplit('/', 1)[-1])


class ReportEmailView(APIView):
    """POST /reports/email/ — email a completed report."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        history_id = request.data.get('history_id')
        recipients = request.data.get('recipients') or []
        subject = request.data.get('subject') or 'AGSuite ERP Report'
        message = request.data.get('message') or ''
        if not history_id:
            return Response({'detail': 'history_id is required.'}, status=status.HTTP_400_BAD_REQUEST)
        if not recipients or not isinstance(recipients, list):
            return Response({'detail': 'recipients must be a non-empty list.'}, status=status.HTTP_400_BAD_REQUEST)

        history = get_object_or_404(ReportHistory, id=history_id, company=request.user.company)
        result = send_report_email_task.delay(
            history_id=str(history.id),
            recipients=recipients,
            subject=subject,
            message=message,
        )
        _audit(request, action=AuditAction.EXPORT, entity='ReportHistory', entity_id=history.id, new_value={'email': True, 'recipients': len(recipients)})
        return success_response(message='Report email dispatched.', data={'task_id': result.id, 'history_id': str(history.id)})
