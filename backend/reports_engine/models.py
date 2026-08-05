"""
Enterprise Reporting Engine models.

Three domain models, all company-scoped:

- ReportTemplate: a saved report configuration (filters, columns,
  sorting, grouping) that users can reuse for repeated reporting.
- ScheduledReport: a report that runs on a schedule (daily/weekly/
  monthly/quarterly/yearly, with a future-ready custom cron field).
- ReportHistory: one row per report generation — tracks who generated
  it, when, the format, status, duration, download_count and file
  metadata.
"""

import uuid

from django.conf import settings
from django.db import models

from tenancy.models import Company


class ReportStatus(models.TextChoices):
    """Lifecycle status of a report generation job."""

    PENDING = 'PENDING', 'Pending'
    PROCESSING = 'PROCESSING', 'Processing'
    COMPLETED = 'COMPLETED', 'Completed'
    FAILED = 'FAILED', 'Failed'
    EXPIRED = 'EXPIRED', 'Expired'


class ReportType(models.TextChoices):
    """Supported report types."""

    SALES = 'SALES', 'Sales Report'
    PURCHASE = 'PURCHASE', 'Purchase Report'
    CUSTOMER = 'CUSTOMER', 'Customer Report'
    VENDOR = 'VENDOR', 'Vendor Report'
    INVENTORY = 'INVENTORY', 'Inventory Report'
    FINANCE = 'FINANCE', 'Finance Report'
    INVOICE = 'INVOICE', 'Invoice Report'
    OCR = 'OCR', 'OCR Report'
    AI_USAGE = 'AI_USAGE', 'AI Usage Report'
    NETSUITE_SYNC = 'NETSUITE_SYNC', 'NetSuite Sync Report'


class ExportFormat(models.TextChoices):
    """Supported export formats."""

    PDF = 'PDF', 'PDF'
    XLSX = 'XLSX', 'Excel (.xlsx)'
    CSV = 'CSV', 'CSV'
    JSON = 'JSON', 'JSON'


class ScheduleFrequency(models.TextChoices):
    """Supported schedule frequencies."""

    DAILY = 'DAILY', 'Daily'
    WEEKLY = 'WEEKLY', 'Weekly'
    MONTHLY = 'MONTHLY', 'Monthly'
    QUARTERLY = 'QUARTERLY', 'Quarterly'
    YEARLY = 'YEARLY', 'Yearly'
    CRON = 'CRON', 'Custom Cron'


class ReportTemplate(models.Model):
    """A saved, reusable report configuration."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='report_templates',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='report_templates_created',
    )
    name = models.CharField(max_length=255)
    report_type = models.CharField(max_length=30, choices=ReportType.choices)
    # JSON: { preset, start_date, end_date, columns, sorting, grouping }
    config = models.JSONField(default=dict, blank=True)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'reports_engine_template'
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['company', '-created_at'], name='re_template_company_idx'),
        ]

    def __str__(self):
        return f'{self.name} ({self.get_report_type_display()})'


class ScheduledReport(models.Model):
    """A report scheduled to run at a fixed frequency."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='scheduled_reports',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='scheduled_reports_created',
    )
    name = models.CharField(max_length=255)
    report_type = models.CharField(max_length=30, choices=ReportType.choices)
    frequency = models.CharField(max_length=20, choices=ScheduleFrequency.choices)
    cron_expression = models.CharField(max_length=100, blank=True, help_text='Future-ready custom cron.')
    # JSON: { preset, start_date, end_date, columns, recipients, subject, message }
    config = models.JSONField(default=dict, blank=True)
    format = models.CharField(max_length=10, choices=ExportFormat.choices, default=ExportFormat.CSV)
    is_active = models.BooleanField(default=True)
    last_run_at = models.DateTimeField(null=True, blank=True)
    next_run_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'reports_engine_schedule'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'is_active'], name='re_schedule_active_idx'),
        ]

    def __str__(self):
        return f'{self.name} ({self.get_frequency_display()})'


class ReportHistory(models.Model):
    """One row per report generation — the audit/history record."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='report_history',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='reports_generated',
    )
    report_type = models.CharField(max_length=30, choices=ReportType.choices)
    format = models.CharField(max_length=10, choices=ExportFormat.choices)
    status = models.CharField(
        max_length=20,
        choices=ReportStatus.choices,
        default=ReportStatus.PENDING,
        db_index=True,
    )
    # Filters as JSON (preset / start_date / end_date).
    filters = models.JSONField(default=dict, blank=True)
    # Metadata captured after generation.
    record_count = models.PositiveIntegerField(default=0)
    file_size = models.PositiveIntegerField(default=0)
    execution_time_ms = models.PositiveIntegerField(default=0)
    file = models.FileField(upload_to='reports/%Y/%m/%d/', null=True, blank=True)
    download_count = models.PositiveIntegerField(default=0)
    error_message = models.TextField(blank=True)
    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'reports_engine_history'
        ordering = ['-generated_at']
        indexes = [
            models.Index(fields=['company', '-generated_at'], name='re_history_company_idx'),
            models.Index(fields=['company', 'status'], name='re_history_status_idx'),
        ]

    def __str__(self):
        return f'{self.get_report_type_display()} — {self.get_status_display()}'
