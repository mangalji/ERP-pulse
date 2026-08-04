"""
Notification models — foundation only.

No sending/notification logic is implemented here. The models store
notification records and per-user preferences for a future notification
service.
"""

from django.conf import settings
from django.db import models

from tenancy.models import Company


class NotificationType(models.TextChoices):
    """Notification types."""

    INFO = 'INFO', 'Info'
    SUCCESS = 'SUCCESS', 'Success'
    WARNING = 'WARNING', 'Warning'
    ERROR = 'ERROR', 'Error'
    SYSTEM = 'SYSTEM', 'System'


class Notification(models.Model):
    """A single notification record for a user."""

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notifications',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
    )
    title = models.CharField(max_length=255)
    message = models.TextField()
    type = models.CharField(
        max_length=20,
        choices=NotificationType.choices,
        default=NotificationType.INFO,
    )
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'notification'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at'], name='notif_user_recent_idx'),
            models.Index(fields=['user', 'is_read'], name='notif_user_unread_idx'),
        ]

    def __str__(self) -> str:
        return f'{self.title} → {self.user.email}'


class NotificationPreference(models.Model):
    """Per-user notification preferences."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notification_preferences',
    )
    category = models.CharField(max_length=100)
    email_enabled = models.BooleanField(default=True)
    in_app_enabled = models.BooleanField(default=True)
    push_enabled = models.BooleanField(default=True)

    class Meta:
        db_table = 'notification_preference'
        constraints = [
            models.UniqueConstraint(fields=['user', 'category'], name='unique_user_category'),
        ]

    def __str__(self) -> str:
        return f'{self.user.email} ({self.category})'