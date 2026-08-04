"""
Company model for the tenancy app.

``Company`` represents a tenant organization in the ERP Pulse platform.
Each company is a distinct tenant with its own users, NetSuite
connections, and data. This is the foundation for multi-tenancy.

The model inherits from ``core.models.BaseModel`` which provides:
- UUID primary key (``id``)
- Timestamps (``created_at``, ``updated_at``)
- Soft-delete fields (``is_deleted``, ``deleted_at``)
- Audit user tracking (``created_by``, ``updated_by``)
"""

from django.conf import settings
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver

from core.models import BaseModel

class CompanyStatus(models.TextChoices):
    TRIAL = "TRIAL", "Trial"
    ACTIVE = "ACTIVE", "Active"
    SUSPENDED = "SUSPENDED", "Suspended"
    EXPIRED = "EXPIRED", "Expired"

class Company(BaseModel):
    """
    A tenant organization in the ERP Pulse platform.

    Each Company is a distinct tenant. Users belong to a Company via
    a future FK on the User model. NetSuite connections and all
    tenant-scoped data will reference this model.
    """

    Status = CompanyStatus

    name = models.CharField(max_length=255, help_text="Display name of the client company.")
    code = models.CharField(max_length=50, unique=True, db_index=True, help_text="Unique immutable company identifier.")
    status = models.CharField(max_length=20,choices=CompanyStatus.choices,default=CompanyStatus.TRIAL,db_index=True)
    contact_email = models.EmailField(
        blank=True,
        null=True,
    )

    contact_phone = models.CharField(
        max_length=20,
        blank=True,
    )

    country = models.CharField(
        max_length=100,
        blank=True,
    )

    class Meta:
        db_table = "company"
        ordering = ["name"]
        verbose_name = "Company"
        verbose_name_plural = "Companies"

    def __str__(self):
        return f"{self.name} ({self.code})"


class Module(BaseModel):
    """A feature module that can be enabled/disabled per company."""

    name = models.CharField(max_length=150, unique=True)
    code = models.CharField(max_length=100, unique=True)
    display_name = models.CharField(max_length=255, blank=True)
    icon = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    is_system = models.BooleanField(default=False)

    class Meta:
        db_table = "module"
        ordering = ["sort_order", "name"]
        verbose_name = "Module"
        verbose_name_plural = "Modules"

    def __str__(self):
        return f"{self.name} ({self.code})"


class CompanyModule(BaseModel):
    """Links a Company to a Module with enable/disable and usage limits."""

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="company_modules")
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name="company_modules")
    enabled = models.BooleanField(default=True)
    usage_limit = models.PositiveIntegerField(null=True, blank=True)
    activated_at = models.DateTimeField(null=True, blank=True)
    activated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
    )

    class Meta:
        db_table = "company_module"
        constraints = [
            models.UniqueConstraint(fields=["company", "module"], name="unique_company_module"),
        ]
        verbose_name = "Company Module"
        verbose_name_plural = "Company Modules"

    def __str__(self):
        return f"{self.company.name} → {self.module.name}"


class CompanySettings(BaseModel):
    """Per-company configuration settings."""

    company = models.OneToOneField(
        Company,
        on_delete=models.CASCADE,
        related_name='settings',
    )
    timezone = models.CharField(max_length=100, default='UTC')
    currency = models.CharField(max_length=10, default='INR')
    language = models.CharField(max_length=10, default='en')
    date_format = models.CharField(max_length=20, default='DD/MM/YYYY')
    number_format = models.CharField(max_length=20, default='en-IN')

    class Meta:
        db_table = 'company_settings'
        verbose_name = 'Company Settings'
        verbose_name_plural = 'Company Settings'

    def __str__(self):
        return f'{self.company.name} settings'


@receiver(post_save, sender=Company)
def create_company_settings(sender, instance, created, **kwargs):
    """Automatically create default settings when a Company is created."""
    if created:
        CompanySettings.objects.get_or_create(company=instance)
