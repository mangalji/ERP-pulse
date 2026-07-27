"""
Reusable email sending utility.

This module intentionally contains only low-level email sending functionality.
Business logic (OTP emails, welcome emails, password reset emails, etc.)
must remain inside their respective services.
"""

import logging

from django.core.mail import send_mail
from django.conf import settings

logger = logging.getLogger(__name__)

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
    
    try:
        return send_mail(
            subject = subject,
            message = message,
            from_email = from_email or settings.DEFAULT_FROM_EMAIL,
            recipient_list= recipient_list,
            fail_silently=fail_silently,
        )
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
