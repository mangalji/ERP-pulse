"""
Reports Engine Celery tasks.

Large report generation runs asynchronously so HTTP requests are never
blocked. Uses Celery if available; otherwise falls back to no-op
placeholders so the module imports cleanly without Celery.

Three tasks:
- generate_report_task: run a single report generation + export.
- scheduled_report_task: run a scheduled report (dispatch + record run).
- send_report_email_task: email a generated report to recipients.
"""

import logging
import time

from django.core.files.base import ContentFile

from audit.models import AuditAction
from audit.services import audit_service
from reports_engine.models import ReportHistory, ReportStatus, ScheduledReport
from reports_engine.services.email_service import ReportEmailService
from reports_engine.services.export_service import ExportService
from reports_engine.services.report_service import generate_report_data
from reports_engine.services.schedule_service import ScheduleService

logger = logging.getLogger(__name__)

try:
    from celery import shared_task

    @shared_task(bind=True, max_retries=3, default_retry_delay=60)
    def generate_report_task(self, history_id: str) -> dict:
        """Generate and export a report for an existing ReportHistory row."""
        try:
            history = ReportHistory.objects.get(id=history_id)
        except ReportHistory.DoesNotExist:
            logger.error('ReportHistory %s not found.', history_id)
            return {'status': 'not_found'}

        history.status = ReportStatus.PROCESSING
        history.save(update_fields=['status'])

        start_ms = time.time() * 1000
        try:
            payload = generate_report_data(
                report_type=history.report_type,
                user=history.created_by,
                **history.filters,
            )
            data, _mime, ext = ExportService().export(payload=payload, fmt=history.format)

            filename = f'report_{history.id.hex}.{ext}'
            history.file.save(filename, ContentFile(data), save=False)
            history.record_count = len(payload.get('rows', []))
            history.file_size = len(data)
            history.execution_time_ms = int(time.time() * 1000 - start_ms)
            history.status = ReportStatus.COMPLETED
            history.save()

            audit_service.log(
                module='reports',
                action=AuditAction.EXPORT,
                entity='ReportHistory',
                entity_id=str(history.id),
                company=history.company,
                user=history.created_by,
                new_value={'status': history.status, 'record_count': history.record_count},
            )
            return {'status': 'completed', 'history_id': str(history.id)}

        except Exception as exc:
            logger.exception('Report generation failed for %s', history_id)
            history.status = ReportStatus.FAILED
            history.error_message = str(exc)[:500]
            history.execution_time_ms = int(time.time() * 1000 - start_ms)
            history.save(update_fields=['status', 'error_message', 'execution_time_ms'])
            raise self.retry(exc=exc, countdown=2 ** self.request.retries * 60)

    @shared_task(bind=True, max_retries=3, default_retry_delay=60)
    def scheduled_report_task(self, schedule_id: str) -> dict:
        """Run a scheduled report: generate + email if configured."""
        try:
            schedule = ScheduledReport.objects.get(id=schedule_id)
        except ScheduledReport.DoesNotExist:
            logger.error('ScheduledReport %s not found.', schedule_id)
            return {'status': 'not_found'}

        if not schedule.is_active:
            return {'status': 'inactive'}

        history = ReportHistory.objects.create(
            company=schedule.company,
            created_by=schedule.created_by,
            report_type=schedule.report_type,
            format=schedule.format,
            status=ReportStatus.PENDING,
            filters=schedule.config,
        )

        ScheduleService().record_run(schedule=schedule)

        result = generate_report_task.delay(history_id=str(history.id))

        config = schedule.config or {}
        recipients = config.get('recipients') or []
        if recipients:
            send_report_email_task.delay(
                history_id=str(history.id),
                recipients=recipients,
                subject=config.get('subject') or f'Scheduled Report: {schedule.name}',
                message=config.get('message') or '',
            )

        return {'status': 'dispatched', 'task_id': result.id, 'history_id': str(history.id)}

    @shared_task(bind=True, max_retries=3, default_retry_delay=60)
    def send_report_email_task(
        self,
        history_id: str,
        recipients: list[str],
        subject: str,
        message: str,
    ) -> dict:
        """Email a completed report to recipients."""
        try:
            history = ReportHistory.objects.get(id=history_id)
        except ReportHistory.DoesNotExist:
            logger.error('ReportHistory %s not found for email.', history_id)
            return {'status': 'not_found'}

        if history.status != ReportStatus.COMPLETED or not history.file:
            logger.warning('Report %s not ready for email (status=%s).', history_id, history.status)
            return {'status': 'not_ready'}

        attachment_path = history.file.name
        service = ReportEmailService()
        sent = service.send_report(
            recipients=recipients,
            subject=subject,
            message=message,
            attachment_path=attachment_path,
            attachment_name=history.file.name.rsplit('/', 1)[-1],
            fail_silently=True,
        )

        audit_service.log(
            module='reports',
            action=AuditAction.EXPORT,
            entity='ReportHistory',
            entity_id=str(history.id),
            company=history.company,
            user=history.created_by,
            new_value={'emailed': True, 'recipients': len(recipients), 'sent': sent},
        )
        return {'status': 'sent', 'sent': sent, 'history_id': str(history_id)}

except ImportError:
    # Celery not installed — no-op placeholders so imports still work.
    def generate_report_task(history_id: str) -> dict:
        logger.warning('Celery not installed; generate_report_task is a no-op.')
        return {'status': 'noop'}

    def scheduled_report_task(schedule_id: str) -> dict:
        logger.warning('Celery not installed; scheduled_report_task is a no-op.')
        return {'status': 'noop'}

    def send_report_email_task(*, history_id: str, recipients: list[str], subject: str, message: str) -> dict:
        logger.warning('Celery not installed; send_report_email_task is a no-op.')
        return {'status': 'noop'}
