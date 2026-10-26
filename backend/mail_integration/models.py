"""Persistent mailbox connections and temporary incoming-email staging."""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models

from common.crypto import EncryptedTextField


class EmailIntegration(models.Model):
    """One OAuth-connected mailbox belonging to a company."""

    DEFAULT_SYNC_INTERVAL_MINUTES = 30

    class Provider(models.TextChoices):
        GOOGLE = "GOOGLE", "Google Gmail"
        ZOHO = "ZOHO", "Zoho Mail"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        CONNECTED = "CONNECTED", "Connected"
        ERROR = "ERROR", "Error"
        DISCONNECTED = "DISCONNECTED", "Disconnected"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(
        "tenancy.Company",
        on_delete=models.CASCADE,
        related_name="email_integrations",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_email_integrations",
    )
    provider = models.CharField(max_length=20, choices=Provider.choices)
    # The saved OCR template is snapshotted into every email-created batch.
    ocr_template = models.ForeignKey(
        "ocr.OCRExtractionTemplate",
        on_delete=models.PROTECT,
        related_name="email_integrations",
        null=True,
        blank=True,
    )
    mailbox_email = models.EmailField()
    display_name = models.CharField(max_length=255, blank=True, default="")
    provider_metadata = models.JSONField(default=dict, blank=True)
    oauth_client_id = models.CharField(max_length=255, blank=True, default="")
    oauth_client_secret = EncryptedTextField(null=True, blank=True)
    access_token = EncryptedTextField(null=True, blank=True)
    refresh_token = EncryptedTextField(null=True, blank=True)
    access_token_expires_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    is_active = models.BooleanField(default=False)
    is_paused = models.BooleanField(default=False)
    sync_interval_minutes = models.PositiveSmallIntegerField(default=DEFAULT_SYNC_INTERVAL_MINUTES)
    initial_sync_from_at = models.DateTimeField(null=True, blank=True)
    last_successful_sync_at = models.DateTimeField(null=True, blank=True)
    provider_cursor = models.TextField(blank=True, default="")
    next_sync_at = models.DateTimeField(null=True, blank=True, db_index=True)
    last_error = models.TextField(blank=True, default="")
    consecutive_failures = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "email_integration"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "provider", "mailbox_email"],
                name="unique_company_email_mailbox",
            ),
        ]
        indexes = [
            models.Index(fields=["is_active", "next_sync_at"], name="email_int_due_sync_idx"),
            models.Index(fields=["company", "status"], name="email_int_company_status_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.mailbox_email} ({self.provider})"


class EmailMessage(models.Model):
    """Temporary staging record retained through promotion and short deduplication."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    integration = models.ForeignKey(EmailIntegration, on_delete=models.CASCADE, related_name="messages")
    provider_message_id = models.CharField(max_length=512, blank=True, default="")
    provider_thread_id = models.CharField(max_length=512, blank=True, default="")
    internet_message_id = models.CharField(max_length=1024, blank=True, default="")
    sender_email = models.EmailField(blank=True, default="")
    recipient_emails = models.JSONField(default=list, blank=True)
    subject = models.TextField(blank=True, default="")
    sent_at = models.DateTimeField(null=True, blank=True)
    received_at = models.DateTimeField(null=True, blank=True, db_index=True)
    raw_body = models.TextField(blank=True, default="")
    normalized_body = models.TextField(blank=True, default="")
    body_hash = models.CharField(max_length=64, db_index=True)
    is_vendor_bill = models.BooleanField(null=True, blank=True, db_index=True)
    ai_extracted_data_json = models.JSONField(null=True, blank=True)
    # Terminal rows are retained briefly so an overlapping mailbox sync cannot
    # stage and send the same provider message through AI again.
    dedupe_syncs_remaining = models.PositiveSmallIntegerField(null=True, blank=True, db_index=True)

    # Worker-safety controls, not extraction/validation/posting workflow state.
    lease_owner = models.CharField(max_length=80, blank=True, default="")
    lease_expires_at = models.DateTimeField(null=True, blank=True, db_index=True)
    attempt_count = models.PositiveSmallIntegerField(default=0)
    next_attempt_at = models.DateTimeField(null=True, blank=True, db_index=True)
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "email_message"
        constraints = [
            models.UniqueConstraint(
                fields=["integration", "provider_message_id"],
                condition=~models.Q(provider_message_id=""),
                name="unique_email_provider_message",
            ),
        ]
        indexes = [
            models.Index(fields=["integration", "received_at"], name="email_msg_int_recv_idx"),
            models.Index(fields=["is_vendor_bill", "next_attempt_at"], name="email_msg_ready_attempt_idx"),
        ]

    def __str__(self) -> str:
        return self.subject or self.provider_message_id or str(self.id)
