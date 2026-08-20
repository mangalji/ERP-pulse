from django.db import models
from django.conf import settings


class CompanySize(models.TextChoices):
    """Predefined company size bands for a demo request."""

    SMALL = "1-10", "1-10 employees"
    MEDIUM = "11-50", "11-50 employees"
    LARGE = "51-200", "51-200 employees"
    XLARGE = "201-500", "201-500 employees"
    ENTERPRISE = "500+", "500+ employees"


class Industry(models.TextChoices):
    """Predefined industries for a demo request."""

    TECHNOLOGY = "TECHNOLOGY", "Technology"
    MANUFACTURING = "MANUFACTURING", "Manufacturing"
    RETAIL = "RETAIL", "Retail"
    FINANCE = "FINANCE", "Finance"
    HEALTHCARE = "HEALTHCARE", "Healthcare"
    LOGISTICS = "LOGISTICS", "Logistics"
    ECOMMERCE = "ECOMMERCE", "E-commerce"
    SERVICES = "SERVICES", "Professional Services"
    OTHER = "OTHER", "Other"


class DemoRequest(models.Model):
    class Status(models.TextChoices):
        NEW = "NEW", "New"
        CONTACTED = "CONTACTED", "Contacted"
        DEMO_SCHEDULED = "DEMO_SCHEDULED", "Demo Scheduled"
        DEMO_COMPLETED = "DEMO_COMPLETED", "Demo Completed"
        PROPOSAL_SENT = "PROPOSAL_SENT", "Proposal Sent"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"
        ONBOARDED = "ONBOARDED", "Onboarded"

    #: Terminal statuses — a request in one of these states is considered
    #: "closed" and no longer counts as an active duplicate.
    CLOSED_STATUSES = (Status.APPROVED, Status.REJECTED, Status.ONBOARDED)

    demo_request_number = models.CharField(max_length=20, unique=True, blank=True)

    company_name = models.CharField(max_length=255)
    contact_person = models.CharField(max_length=255)
    business_email = models.EmailField(max_length=40)
    phone = models.CharField(max_length=15)

    industry = models.CharField(
        max_length=30,
        choices=Industry.choices,
        blank=True,
    )
    company_size = models.CharField(
        max_length=20,
        choices=CompanySize.choices,
        blank=True,
    )

    city = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, default="India")

    message = models.TextField(blank=True)

    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.NEW,
    )

    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_demo_requests",
    )

    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "demo_request"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.demo_request_number} - {self.company_name}"
