"""
Email configuration for ERP Pulse.
 
Backend selection (see common/services/email_service.py for the
actual branching logic):
 
1. Brevo HTTP API (BREVO_API_KEY set) — sends over HTTPS (port 443).
   Needed for hosts like Render's free tier, which as of Sept 2025
   blocks outbound traffic on SMTP ports 25/465/587 entirely — SMTP
   delivery just times out there, silently, no matter how correct the
   EMAIL_HOST/EMAIL_HOST_USER/EMAIL_HOST_PASSWORD values are.
2. SMTP (EMAIL_HOST set, BREVO_API_KEY not set) — traditional SMTP
   delivery, for environments without that port restriction.
3. Console backend (neither set) — prints to stdout, for local dev.
"""

from decouple import config
import os

# ------------------------------------------------------------
# Select Email Backend
# ------------------------------------------------------------

# ------------------------------------------------------------
# Brevo HTTP API (see docstring above for why this exists)
# ------------------------------------------------------------
 
BREVO_API_KEY = config("BREVO_API_KEY", default="")
 
# Shared by both the Brevo HTTP client and Django's SMTP backend.
EMAIL_TIMEOUT = config(
    "EMAIL_TIMEOUT",
    default=10,
    cast=int,
)

if config("EMAIL_HOST", default=""):

    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"

    EMAIL_HOST = config("EMAIL_HOST")

    EMAIL_PORT = config(
        "EMAIL_PORT",
        default=587,
        cast=int,
    )

    EMAIL_HOST_USER = config("EMAIL_HOST_USER")

    EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD")

    EMAIL_USE_TLS = config(
        "EMAIL_USE_TLS",
        default=True,
        cast=bool,
    )

else:

    EMAIL_BACKEND = (
        "django.core.mail.backends.console.EmailBackend"
    )

# ------------------------------------------------------------
# Default Sender
# ------------------------------------------------------------

DEFAULT_FROM_EMAIL = config(
    "DEFAULT_FROM_EMAIL",
    default="noreply@erppulse.local",
)

# Brevo's API requires a sender display name alongside the address.
DEFAULT_FROM_NAME = config(
    "DEFAULT_FROM_NAME",
    default="ERP Pulse",
)
 