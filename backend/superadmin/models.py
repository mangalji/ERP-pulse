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
    Subscription plan that defines pricing and validity for a company.
    """
    name = models.CharField(max_length=150, unique=True)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    validity_days = models.PositiveIntegerField(default=30)
    monthly_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    yearly_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    max_employees = models.PositiveIntegerField(default=0)
    max_ocr_documents = models.PositiveIntegerField(default=0)
    max_storage_gb = models.PositiveIntegerField(default=0)  # in GB
    trial_days = models.PositiveIntegerField(default=14, help_text='Number of trial days for new assignments')
    ai_credits = models.PositiveIntegerField(default=0, help_text='AI credits included per billing cycle')
    ocr_credits = models.PositiveIntegerField(default=0, help_text='OCR documents allowed per billing cycle')
    enabled_models = models.ManyToManyField(Module, related_name='plans', blank=True)
    status = models.CharField(max_length=20, choices=PlanStatus.choices, default=PlanStatus.ACTIVE)

    Status = PlanStatus

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
    REPLACED = 'REPLACED', 'Replaced'


class DiscountType(models.TextChoices):
    NONE = 'NONE', 'No Discount'
    PERCENTAGE = 'PERCENTAGE', 'Percentage'
    FIXED = 'FIXED', 'Fixed Amount'


class BillingCycle(models.TextChoices):
    MONTHLY = 'MONTHLY', 'Monthly'
    YEARLY = 'YEARLY', 'Yearly'


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
    discount_type = models.CharField(max_length=20, choices=DiscountType.choices, default=DiscountType.NONE)
    discount_value = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    billing_cycle = models.CharField(max_length=20, choices=BillingCycle.choices, default=BillingCycle.MONTHLY)
    original_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    final_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    validity_days = models.PositiveIntegerField(default=30)
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_plans',
    )

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


class SubscriptionHistory(BaseModel):
    """
    Read-only historical record of every plan assignment/upgrade/downgrade.
    Never overwritten — a new entry is always created for each change.
    """
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='subscription_history')
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name='subscription_history')
    company_plan = models.ForeignKey(
        CompanyPlan, on_delete=models.SET_NULL, null=True, blank=True, related_name='history_entries'
    )
    original_price = models.DecimalField(max_digits=10, decimal_places=2)
    discount_type = models.CharField(max_length=20, choices=DiscountType.choices, default=DiscountType.NONE)
    discount_value = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    final_price = models.DecimalField(max_digits=10, decimal_places=2)
    billing_cycle = models.CharField(max_length=20, choices=BillingCycle.choices, default=BillingCycle.MONTHLY)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='subscription_history_entries',
    )
    status_before = models.CharField(max_length=20, choices=CompanyPlanStatus.choices, default=CompanyPlanStatus.ACTIVE)
    status_after = models.CharField(max_length=20, choices=CompanyPlanStatus.choices, default=CompanyPlanStatus.ACTIVE)
    change_type = models.CharField(max_length=30, help_text='assign, upgrade, downgrade, renew, cancel')

    class Meta:
        db_table = 'sa_subscription_history'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.company.name} - {self.change_type} - {self.plan.name}'


class PaymentStatus(models.TextChoices):
    PENDING = 'PENDING', 'Pending'
    SUCCESS = 'SUCCESS', 'Success'
    FAILED = 'FAILED', 'Failed'
    REFUNDED = 'REFUNDED', 'Refunded'


class TransactionStatus(models.TextChoices):
    INITIATED = 'INITIATED', 'Initiated'
    COMPLETED = 'COMPLETED', 'Completed'
    PENDING = 'PENDING', 'Pending'
    FAILED = 'FAILED', 'Failed'
    REFUNDED = 'REFUNDED', 'Refunded'


class Transaction(BaseModel):
    """
    Read-only transaction record for plan assignments and payments.
    Prepared for future payment gateway integration (Razorpay, Stripe, Manual).
    """
    TRANSACTION_ID_PREFIX = 'TXN'

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='transactions')
    subscription_history = models.ForeignKey(
        SubscriptionHistory, on_delete=models.SET_NULL, null=True, blank=True, related_name='transactions'
    )
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name='transactions', null=True, blank=True)
    transaction_id = models.CharField(max_length=64, unique=True)
    original_amount = models.DecimalField(max_digits=10, decimal_places=2)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    final_amount = models.DecimalField(max_digits=10, decimal_places=2)
    billing_cycle = models.CharField(max_length=20, choices=BillingCycle.choices, default=BillingCycle.MONTHLY)
    payment_status = models.CharField(max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.PENDING)
    transaction_status = models.CharField(max_length=20, choices=TransactionStatus.choices, default=TransactionStatus.INITIATED)
    payment_method = models.CharField(max_length=50, default='MANUAL', help_text='Razorpay, Stripe, Manual, etc.')
    discount_type = models.CharField(max_length=20, choices=DiscountType.choices, default=DiscountType.NONE)
    discount_value = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_transactions',
    )
    invoice_number = models.CharField(max_length=64, blank=True, help_text='GST invoice number if applicable')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'sa_transaction'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.transaction_id} - {self.company.name} - {self.final_amount}'

    @property
    def discount_amount_value(self):
        return self.original_amount - self.final_amount


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
