from django.db import models
from django.conf import settings
from tenancy.models import Company
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
    status = models.CharField(max_length=20, choices=PlanStatus.choices, default=PlanStatus.ACTIVE)

    Status = PlanStatus

    class Meta:
        db_table = 'subscription_plans'
        ordering = ['name']

    def __str__(self):
        return self.name


class DiscountType(models.TextChoices):
    NONE = 'NONE', 'No Discount'
    PERCENTAGE = 'PERCENTAGE', 'Percentage'
    FIXED = 'FIXED', 'Fixed Amount'


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
    Transaction record for company plan assignment and payment tracking.
    """
    TRANSACTION_ID_PREFIX = 'TXN'

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='transactions')
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name='transactions', null=True, blank=True)
    transaction_id = models.CharField(max_length=64, unique=True)
    original_amount = models.DecimalField(max_digits=10, decimal_places=2)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_status = models.CharField(max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.PENDING)
    transaction_status = models.CharField(max_length=20, choices=TransactionStatus.choices, default=TransactionStatus.INITIATED)
    payment_method = models.CharField(max_length=50, default='MANUAL', help_text='Razorpay, Stripe, Manual, etc.')
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
        db_table = 'subscription_plan_transaction'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.transaction_id} - {self.company.name} - {self.total_amount}'
