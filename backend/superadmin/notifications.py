import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Q

from common.email_service import send_email
from superadmin.models import Transaction
from tenancy.models import Company

logger = logging.getLogger(__name__)
User = get_user_model()


def _company_admin_emails(company_id):
    return list(
        User.objects.filter(
            company_id=company_id,
            role__name__iexact="Company Admin",
        )
        .exclude(email__isnull=True)
        .exclude(email__exact="")
        .values_list("email", flat=True)
        .distinct()
    )


def _send(*, subject, message, recipients, context):
    if not recipients:
        logger.info("No recipients for %s email (%s).", context, subject)
        return

    try:
        send_email(
            subject=subject,
            message=message,
            recipient_list=recipients,
            fail_silently=True,
        )
    except Exception:
        logger.exception("Failed to send %s email to %s.", context, recipients)


def _support_email():
    main_superadmin_email = (
        User.objects.filter(
            is_active=True,
            company__isnull=True,
        )
        .filter(
            Q(is_superuser=True)
            | Q(is_staff=True)
            | Q(role__name__iexact="Super Admin")
        )
        .order_by("-is_superuser", "-is_staff", "created_at", "email")
        .values_list("email", flat=True)
        .first()
    )
    return main_superadmin_email or settings.DEFAULT_FROM_EMAIL


def send_company_created_email(company_id):
    company = Company.objects.filter(pk=company_id).only(
        "name", "code", "contact_email", "status"
    ).first()
    if not company or not company.contact_email:
        return

    _send(
        subject=f"Your AGSuite company has been created: {company.name}",
        message=(
            f"Hello,\n\n"
            f"Your company, {company.name}, has been created on AGSuite ERP.\n\n"
            f"Company code: {company.code}\n"
            f"Current status: {company.status}\n\n"
            "A Company Admin account and subscription setup can now be completed by the AGSuite team.\n\n"
            f"For assistance, contact { _support_email() }.\n\n"
            "Regards,\nAGSuite Team"
        ),
        recipients=[company.contact_email],
        context="company-created",
    )


def send_company_suspended_email(company_id, description):
    company = Company.objects.filter(pk=company_id).only("name").first()
    if not company:
        return

    _send(
        subject=f"Your company has been suspended: {company.name}",
        message=(
            f"Hello,\n\n"
            f"Your company, {company.name}, has been suspended by an AGSuite Super Admin.\n\n"
            f"Reason: {description}\n\n"
            "All company operations are temporarily unavailable. Access and operations will resume after the company is activated again.\n\n"
            f"Please contact the AGSuite Super Admin team at {_support_email()} for assistance.\n\n"
            "Regards,\nAGSuite Team"
        ),
        recipients=_company_admin_emails(company_id),
        context="company-suspended",
    )


def send_company_activated_email(company_id):
    company = Company.objects.filter(pk=company_id).only("name").first()
    if not company:
        return

    _send(
        subject=f"Your company has been activated: {company.name}",
        message=(
            f"Hello,\n\n"
            f"Your company, {company.name}, has been activated again on AGSuite ERP.\n\n"
            "Company operations and access are now available.\n\n"
            f"For assistance, contact {_support_email()}.\n\n"
            "Regards,\nAGSuite Team"
        ),
        recipients=_company_admin_emails(company_id),
        context="company-activated",
    )


def send_transaction_completed_email(transaction_id):
    transaction = (
        Transaction.objects.select_related("company", "plan")
        .filter(pk=transaction_id)
        .first()
    )
    if not transaction or not transaction.plan:
        return

    company = transaction.company
    plan = transaction.plan
    _send(
        subject=f"Payment completed and plan assigned: {company.name}",
        message=(
            f"Hello,\n\n"
            f"The final transaction for {company.name} has been completed successfully.\n\n"
            f"Plan: {plan.name}\n"
            f"Plan description: {plan.description or '—'}\n"
            f"Validity: {plan.validity_days} days\n"
            f"Original amount: ₹{transaction.original_amount}\n"
            f"Discount: ₹{transaction.discount_amount}\n"
            f"Final amount: ₹{transaction.total_amount}\n"
            f"Transaction ID: {transaction.transaction_id}\n"
            f"Plan starts: {company.plan_start_date}\n"
            f"Plan ends: {company.plan_end_date}\n\n"
            f"For assistance, contact {_support_email()}.\n\n"
            "Regards,\nAGSuite Team"
        ),
        recipients=_company_admin_emails(company.id),
        context="transaction-completed",
    )
