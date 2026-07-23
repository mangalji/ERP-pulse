"""
Models for the Sync Manager (P1).

SyncRun is one row per sync execution against a NetSuiteConnection.
SyncStage is one row per entity type (customer, invoice, ...) within
that run — this is what makes "retry only failed stages" possible: a
run where customers synced fine but invoices failed can be retried by
re-running just the invoice stage, not the whole thing.

No NetSuite business data (actual customer/invoice records) is stored
here — only sync bookkeeping (what ran, when, how many records, what
failed). Matches the project-wide rule that NetSuite business data is
never persisted locally (NETSUITE_CONTEXT.md).
"""

import uuid

from django.conf import settings
from django.db import models

from netsuite.models import NetSuiteConnection


class SyncRun(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('success', 'Success'),
        ('partial_failure', 'Partial Failure'),
        ('failed', 'Failed'),
    ]

    TRIGGER_CHOICES = [
        ('manual', 'Manual'),
        ('scheduled', 'Scheduled'),  # not yet triggerable — see sync/services.py docstring
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    connection = models.ForeignKey(
        NetSuiteConnection,
        on_delete=models.CASCADE,
        related_name='sync_runs',
    )
    triggered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='triggered_sync_runs',
    )

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    trigger = models.CharField(max_length=20, choices=TRIGGER_CHOICES, default='manual')

    records_processed = models.PositiveIntegerField(default=0)
    records_failed = models.PositiveIntegerField(default=0)

    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'sync_run'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['connection', '-created_at'], name='sync_run_connection_idx'),
        ]

    def __str__(self):
        return f'SyncRun {self.id} ({self.status})'


class SyncStage(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('success', 'Success'),
        ('failed', 'Failed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    run = models.ForeignKey(SyncRun, on_delete=models.CASCADE, related_name='stages')
    record_type = models.CharField(max_length=50)  # a netsuite.constants.NetSuiteRecordType value

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    records_processed = models.PositiveIntegerField(default=0)
    error_message = models.TextField(null=True, blank=True)

    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'sync_stage'
        ordering = ['id']
        constraints = [
            models.UniqueConstraint(fields=['run', 'record_type'], name='unique_run_record_type'),
        ]

    def __str__(self):
        return f'{self.record_type} ({self.status}) — run {self.run_id}'
