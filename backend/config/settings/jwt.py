"""
JWT configuration for ERP Pulse.

Uses:
- djangorestframework-simplejwt
"""

from datetime import timedelta

from decouple import config


# ------------------------------------------------------------------
# Simple JWT
# ------------------------------------------------------------------

SIMPLE_JWT = {
    # Access Token
    "ACCESS_TOKEN_LIFETIME": timedelta(
        minutes=config(
            "JWT_ACCESS_TOKEN_LIFETIME_MINUTES",
            default=15,
            cast=int,
        )
    ),

    # Refresh Token
    "REFRESH_TOKEN_LIFETIME": timedelta(
        days=config(
            "JWT_REFRESH_TOKEN_LIFETIME_DAYS",
            default=7,
            cast=int,
        )
    ),

    # Refresh Behaviour
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,

    # Header
    "AUTH_HEADER_TYPES": ("Bearer",),

    # Optional Future Settings
    "UPDATE_LAST_LOGIN": False,
}