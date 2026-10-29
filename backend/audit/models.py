"""
Audit log model — foundation only.

No automatic logging is implemented yet. The ``AuditLog`` model stores
one row per auditable action. A reusable ``AuditService`` is provided
in ``audit/services.py`` for manual logging.
"""

from django.conf import settings
from django.db import models

from tenancy.models import Company


class AuditModule(models.TextChoices):
    """Modules that can produce audit events."""

    COMPANY = 'company', 'Company'
    EMPLOYEE = 'employee', 'Employee'
    INVOICE = 'invoice', 'Invoice'
    OCR = 'ocr', 'OCR'
    AI = 'ai', 'AI'
    REPORTS = 'reports', 'Reports'
    DASHBOARD = 'dashboard', 'Dashboard'
    NETSUITE = 'netsuite', 'NetSuite'
    SETTINGS = 'settings', 'Settings'
    RBAC = 'rbac', 'RBAC'
    AUTH = 'auth', 'Authentication'
    DEMO = 'demo', 'Demo Request'
    INVITATION = 'invitation', 'Invitation'
    SUBSCRIPTION = 'subscription', 'Subscription'
    EMAIL = 'email', 'Email'
    SCHEDULER = 'scheduler', 'Scheduler'


class AuditAction(models.TextChoices):
    """Actions that can be audited."""

    CREATE = 'create', 'Create'
    UPDATE = 'update', 'Update'
    DELETE = 'delete', 'Delete'
    VIEW = 'view', 'View'
    EXPORT = 'export', 'Export'
    LOGIN = 'login', 'Login'
    LOGOUT = 'logout', 'Logout'
    SYNC = 'sync', 'Sync'
    CONNECT = 'connect', 'Connect'
    DISCONNECT = 'disconnect', 'Disconnect'
    UPLOAD = 'upload', 'Upload'
    REVIEW = 'review', 'Review'
    CHAT = 'chat', 'Chat'
    ASSIGN = 'assign', 'Assign'
    APPROVE = 'approve', 'Approve'
    REJECT = 'reject', 'Reject'
    SEND = 'send', 'Send'
    ACCEPT = 'accept', 'Accept'
    FETCH = 'fetch', 'Fetch'
    PROCESS = 'process', 'Process'
    VALIDATE = 'validate', 'Validate'
    POST = 'post', 'Post'


class AuditActivityType(models.TextChoices):
    MANUAL = 'manual', 'Manual'
    AUTOMATED = 'automated', 'Automated'


class AuditStatus(models.TextChoices):
    SUCCESS = 'success', 'Success'
    FAILED = 'failed', 'Failed'
    INFO = 'info', 'Info'


class AuditLog(models.Model):
    """One row per auditable action within a company."""

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='audit_logs',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs',
    )
    module = models.CharField(max_length=50, choices=AuditModule.choices)
    action = models.CharField(max_length=50, choices=AuditAction.choices)
    entity = models.CharField(max_length=100)
    entity_id = models.CharField(max_length=100, null=True, blank=True)
    old_value = models.JSONField(null=True, blank=True)
    new_value = models.JSONField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=512,null=True,blank=True)
    activity_type = models.CharField(
        max_length=12,
        choices=AuditActivityType.choices,
        default=AuditActivityType.MANUAL,
        db_index=True,
    )
    status = models.CharField(
        max_length=12,
        choices=AuditStatus.choices,
        default=AuditStatus.SUCCESS,
        db_index=True,
    )
    # Structured operational evidence. Credentials, OTP values and raw email
    # bodies are redacted by AuditService before this field is persisted.
    detail = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'audit_log'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', '-created_at'], name='audit_company_recent_idx'),
            models.Index(fields=['user', '-created_at'], name='audit_user_recent_idx'),
            models.Index(fields=['module', 'entity'], name='audit_module_entity_idx'),
            models.Index(fields=['company', 'activity_type', '-created_at'], name='audit_company_type_recent_idx'),
        ]

    def __str__(self) -> str:
        return f'{self.action} {self.entity} ({self.entity_id})'


class Notification(models.Model):
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='notifications')
    message = models.CharField(max_length=500)
    activity_type = models.CharField(max_length=12, choices=[('manual', 'Manual'), ('automated', 'Automated')], null=True, blank=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='notification_activities')
    link = models.CharField(max_length=500, blank=True, default='')
    is_read = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']
        indexes = [models.Index(fields=['recipient', 'company', '-created_at'], name='notif_user_company_recent')]


class IntegrationFailureAlert(models.Model):
    """Delivery state for actionable integration-failure emails.

    This is intentionally separate from ``Notification``: in-app notifications
    are an activity feed, whereas this model prevents duplicate outbound email
    alerts and records when the 24-hour reminder is due.
    """

    class IntegrationType(models.TextChoices):
        EMAIL = 'email', 'Email'
        NETSUITE = 'netsuite', 'NetSuite'
        AI = 'ai', 'AI'

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='integration_failure_alerts',
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='integration_failure_alerts',
    )
    integration_type = models.CharField(max_length=20, choices=IntegrationType.choices)
    connection_id = models.CharField(max_length=100)
    connection_label = models.CharField(max_length=255, blank=True, default='')
    provider = models.CharField(max_length=100, blank=True, default='')
    reconnect_path = models.CharField(max_length=500, blank=True, default='')
    last_error = models.TextField(blank=True, default='')
    is_open = models.BooleanField(default=True, db_index=True)
    failed_at = models.DateTimeField()
    last_delivery_attempt_at = models.DateTimeField(null=True, blank=True)
    last_alert_sent_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'integration_failure_alert'
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'integration_type', 'connection_id'],
                name='integration_failure_alert_unique_connection',
            ),
        ]
        indexes = [
            models.Index(fields=['is_open', 'last_alert_sent_at'], name='int_failure_alert_due_idx'),
            models.Index(fields=['company', 'is_open'], name='int_failure_alert_company_idx'),
        ]
