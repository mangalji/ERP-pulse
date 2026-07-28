"""
Reusable email sending utility.
 
This module intentionally contains only low-level email sending functionality.
Business logic (OTP emails, welcome emails, password reset emails, etc.)
must remain inside their respective services.
 
Two delivery paths, chosen automatically:
 
- Brevo HTTP API (when settings.BREVO_API_KEY is set) — sends over
  HTTPS (port 443). Needed on hosts like Render's free tier, which
  blocks outbound traffic on SMTP ports 25/465/587 entirely, so SMTP
  delivery silently times out there regardless of how correct the
  SMTP credentials are.
- Django's configured EMAIL_BACKEND otherwise (SMTP in most other
  environments, console for local dev) — unchanged from before.
 
fail_silently is handled uniformly here for both paths: we always
catch and log the failure ourselves (so it shows up in server logs
either way), and only re-raise when the caller asked not to fail
silently..
"""

import logging
import requests

from django.core.mail import send_mail
from django.conf import settings

logger = logging.getLogger(__name__)

BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"


def send_email(
        *,
        subject:str,
        message: str,
        recipient_list: list[str],
        from_email:str | None=None,
        fail_silently: bool=False,
        ) -> int:
    """
    Send a plain text email.

    Args:
        subject: Email subject.
        message: Plain text email body.
        recipient_list: List of recipient email addresses.
        from_email: Sender email. Defaults to settings.DEFAULT_FROM_EMAIL.
        fail_silently: Whether Django should suppress email backend exceptions.

    Returns:
        Number of successfully delivered messages.

    Raises:
        Any exception raised by Django's email backend.
    """

    if not recipient_list:
        raise ValueError("recipient list cannot be empty")

    sender_email = from_email or settings.DEFAULT_FROM_EMAIL
    
    try:

        if settings.BREVO_API_KEY:
            _send_via_brevo(
                subject=subject,
                message=message,
                recipient_list=recipient_list,
                sender_email=sender_email
            )
        else:
            send_email(
                subject=subject,
                message=message,
                from_email=sender_email,
                recipient_list=recipient_list,
                fail_silently=False,
            )
        return len(recipient_list)

    except Exception as exc:
        logger.error(
            "Failed to send email to %s (subject='%s'): %s",
            recipient_list,
            subject,
            str(exc)[:500],
        )
        if not fail_silently:
            raise
        return 0

def _send_via_brevo(*, subject: str, message: str, recipient_list: list[str], sender_email: str) -> None:
    """
    POST to Brevo's transactional email API. Raises on any non-2xx
    response or network failure — send_email() above handles logging
    and fail_silently.
    """

    response = requests.post(
        BREVO_API_URL,
        headers={
            "api-key":settings.BREVO_API_KEY,
            "content-type":"application/json",
            "accept":"application/json",
        },
        json = {
            "sender":{
                "name":settings.DEFAULT_FROM_NAME,
                "email":sender_email,
            },
            "to":[{"email":address} for address in recipient_list],
            "subject":subject,
            "textContent":message,
        },
        timeout=settings.EMAIL_TIMEOUT,
    )
    if response.status_code >= 400:
        raise RuntimeError(
            f"Brevo API returned {response.status_code}: {response.text[:300]}"
        )