"""
Email configuration for ERP Pulse.

Supports:

- Console backend (development)
- SMTP backend (production / real email sending)
"""

from decouple import config

# ------------------------------------------------------------
# Select Email Backend
# ------------------------------------------------------------

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

    # Timeout for SMTP connection (in seconds). Prevents worker hangs
    # when the email server is unreachable or slow to respond.
    EMAIL_TIMEOUT = config(
        "EMAIL_TIMEOUT",
        default=10,
        cast=int,
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

