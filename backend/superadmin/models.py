from django.db import models
from django.conf import settings
from tenancy.models import Company, Module
from core.models import BaseModel


class PlanStatus(models.TextChoices):
    ACTIVE = 'ACTIVE', 'Active'
    INACTIVE = 'INACTIVE', 'Inactive'
    ARCHIVED = 'ARCHIVED', 'Archived'


class Plan(BaseModel):
    """
    Subscription plan that defines limits and pricing for a company.
    """
    name = models.CharField(max_length=150, unique=True)
    description = models.TextField(blank=True)
    monthly_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    yearly_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    max_employees = models.PositiveIntegerField(default=0)
    max_ocr_documents = models.PositiveIntegerField(default=0)
    max_storage_gb = models.PositiveIntegerField(default=0)  # in GB
    enabled_models = models.ManyToManyField(Module, related_name='plans', blank=True)
    status = models.CharField(max_length=20, choices=PlanStatus.choices, default=PlanStatus.ACTIVE)

    class Meta:
        db_table = 'sa_plan'
        ordering = ['name']

    def __str__(self):
        return self.name


class CompanyPlanStatus(models.TextChoices):
    ACTIVE = 'ACTIVE', 'Active'
    EXPIRED = 'EXPIRED', 'Expired'
    CANCELLED = 'CANCELLED', 'Cancelled'
    TRIAL = 'TRIAL', 'Trial'


class CompanyPlan(BaseModel):
    """
    Subscription of a company to a plan.
    """
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='company_plans')
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name='company_plans')
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=CompanyPlanStatus.choices, default=CompanyPlanStatus.TRIAL)
    is_auto_renew = models.BooleanField(default=False)

    class Meta:
        db_table = 'sa_company_plan'
        ordering = ['-start_date']
        constraints = [
            models.UniqueConstraint(
                fields=['company'],
                condition=models.Q(status__in=[CompanyPlanStatus.ACTIVE, CompanyPlanStatus.TRIAL]),
                name='unique_active_company_plan'
            )
        ]

    def __str__(self):
        return f'{self.company.name} - {self.plan.name}'


class SupportSessionStatus(models.TextChoices):
    ACTIVE = 'ACTIVE', 'Active'
    ENDED = 'ENDED', 'Ended'
    EXPIRED = 'EXPIRED', 'Expired'


class SupportSession(BaseModel):
    """
    Support session where an AGSuite staff member assists a company.
    """
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='support_sessions')
    support_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='support_sessions_as_support'
    )
    reason = models.TextField()
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=SupportSessionStatus.choices, default=SupportSessionStatus.ACTIVE)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        db_table = 'sa_support_session'
        ordering = ['-started_at']

    def __str__(self):
        return f'Support session for {self.company.name} by {self.support_user.email}'