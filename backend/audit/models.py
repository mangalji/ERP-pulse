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
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'audit_log'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', '-created_at'], name='audit_company_recent_idx'),
            models.Index(fields=['user', '-created_at'], name='audit_user_recent_idx'),
            models.Index(fields=['module', 'entity'], name='audit_module_entity_idx'),
        ]

    def __str__(self) -> str:
        return f'{self.action} {self.entity} ({self.entity_id})'
