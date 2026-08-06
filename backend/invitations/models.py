import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone
from datetime import timedelta

from core.models import BaseModel
from tenancy.models import Company
from rbac.models import Role


class InvitationStatus(models.TextChoices):
    PENDING = 'PENDING', 'Pending'
    ACCEPTED = 'ACCEPTED', 'Accepted'
    EXPIRED = 'EXPIRED', 'Expired'
    CANCELLED = 'CANCELLED', 'Cancelled'


class Invitation(BaseModel):
    """
    Invitation sent to a user to join a company.
    
    The token is a UUID used as a secure, unguessable link.
    Expiry is enforced by the service layer.
    """

    token = models.UUIDField(unique=True, default=uuid.uuid4, editable=False, db_index=True)
    email = models.EmailField(db_index=True)
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='invitations',
    )
    role = models.ForeignKey(
        Role,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='invitations',
    )
    status = models.CharField(
        max_length=20,
        choices=InvitationStatus.choices,
        default=InvitationStatus.PENDING,
        db_index=True,
    )
    expires_at = models.DateTimeField(db_index=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_invitations',
    )

    class Meta:
        db_table = 'invitation'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['email', 'status'], name='invitation_email_status_idx'),
            models.Index(fields=['token', 'status'], name='invitation_token_status_idx'),
        ]

    def __str__(self):
        return f'Invitation for {self.email} to {self.company.name}'

    def is_expired(self):
        return timezone.now() > self.expires_at

    def is_pending(self):
        return self.status == InvitationStatus.PENDING and not self.is_expired()
