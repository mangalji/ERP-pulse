from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.db import transaction
from functools import wraps
import logging
from audit.models import AuditLog
from audit.notifications import document_label, notify
from ocr.models import OCRDocumentVersion, OCRValidationResult, OCRUpload
from netsuite.models import NetSuiteOCRPosting, NetSuiteConnection
from mail_integration.models import EmailMessage, EmailIntegration

logger = logging.getLogger(__name__)


def safe_event(func):
    @wraps(func)
    def wrapped(*args, **kwargs):
        try:
            with transaction.atomic():
                return func(*args, **kwargs)
        except Exception:
            logger.exception('Notification event failed: %s', func.__name__)
    return wrapped


@receiver(post_save, sender=AuditLog)
@safe_event
def audit_event(sender, instance, created, **kwargs):
    if not created or not instance.user_id or not instance.company_id:
        return
    if instance.action in ('create', 'update', 'delete', 'login', 'connect', 'disconnect'):
        notify(instance.user_id, instance.company_id, f'{instance.entity}: {instance.action} successful.', activity_type='manual', actor_id=instance.user_id)


@receiver(post_save, sender=EmailMessage)
@safe_event
def email_fetched(sender, instance, created, **kwargs):
    if created:
        integration = instance.integration
        notify(integration.created_by_id, integration.company_id, f'Email fetched from {instance.sender_email or "unknown sender"}.', '/app/integrations/email', activity_type='automated')


@receiver(post_save, sender=OCRDocumentVersion)
@safe_event
def extraction_saved(sender, instance, created, **kwargs):
    if created and instance.version_number == 1:
        doc = instance.document
        is_email = bool(doc.batch_id and doc.batch.source_type == 'EMAIL')
        notify(doc.user_id, doc.company_id, f'AI extraction completed for {document_label(doc)}.', f'/app/ocr/history/{doc.pk}', activity_type='automated' if is_email else 'manual', actor_id=None if is_email else instance.created_by_id)


@receiver(post_save, sender=OCRValidationResult)
@safe_event
def validation_saved(sender, instance, created, **kwargs):
    if created:
        doc = instance.document
        state = 'completed' if instance.status == 'VALIDATED' else 'failed'
        notify(doc.user_id, doc.company_id, f'Validation {state} for {document_label(doc)}.', f'/app/ocr/history/{doc.pk}')


@receiver(pre_save, sender=NetSuiteOCRPosting)
@safe_event
def previous_posting_status(sender, instance, **kwargs):
    instance._previous_status = sender.objects.filter(pk=instance.pk).values_list('status', flat=True).first() if instance.pk else None


@receiver(post_save, sender=NetSuiteOCRPosting)
@safe_event
def posting_changed(sender, instance, created, **kwargs):
    if instance.status in ('posted', 'error') and instance.status != getattr(instance, '_previous_status', None):
        doc = instance.document
        state = 'completed' if instance.status == 'posted' else 'failed'
        notify(doc.user_id, doc.company_id, f'NetSuite posting {state} for {document_label(doc)}.', f'/app/ocr/history/{doc.pk}')


@receiver(pre_save, sender=EmailIntegration)
@safe_event
def previous_email_status(sender, instance, **kwargs):
    instance._previous_status = sender.objects.filter(pk=instance.pk).values_list('status', flat=True).first() if instance.pk else None


@receiver(post_save, sender=EmailIntegration)
@safe_event
def email_status_changed(sender, instance, created, **kwargs):
    if instance.status == 'ERROR' and getattr(instance, '_previous_status', None) != 'ERROR':
        notify(instance.created_by_id, instance.company_id, f'Email connection {instance.mailbox_email} needs attention. Check the integration page.', '/app/integrations/email')


@receiver(pre_save, sender=NetSuiteConnection)
@safe_event
def previous_netsuite_status(sender, instance, **kwargs):
    instance._previous_status = sender.objects.filter(pk=instance.pk).values_list('status', flat=True).first() if instance.pk else None


@receiver(post_save, sender=NetSuiteConnection)
@safe_event
def netsuite_status_changed(sender, instance, created, **kwargs):
    if instance.status == 'error' and getattr(instance, '_previous_status', None) != 'error':
        notify(instance.user_id, instance.company_id, 'NetSuite connection needs attention. Check your connection.', '/app/integrations/netsuite')


@receiver(pre_save, sender=OCRUpload)
@safe_event
def previous_upload_status(sender, instance, **kwargs):
    instance._previous_status = sender.objects.filter(pk=instance.pk).values_list('status', flat=True).first() if instance.pk else None


@receiver(post_save, sender=OCRUpload)
@safe_event
def upload_status_changed(sender, instance, created, **kwargs):
    if instance.status == 'FAILED' and getattr(instance, '_previous_status', None) != 'FAILED':
        notify(instance.user_id, instance.user.company_id, f'AI extraction failed for {instance.original_filename}. Check the extraction page.', '/app/ocr/history')
