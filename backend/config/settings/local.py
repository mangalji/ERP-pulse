from .base import *
from decouple import config

DEBUG = True

from .database import LOCAL_DATABASE

DATABASES = {
    "default": LOCAL_DATABASE
}

TEMPLATES[0]["OPTIONS"]["debug"] = True

INTERNAL_IPS = [
    "127.0.0.1",
]

# Local development cache
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "erp-pulse-local-cache",
    }
}

# HTTPS is terminated by Cloudflare Tunnel during remote demos.
JWT_AUTH_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True

# Local browser development normally uses Lax.  A frontend and backend on
# separate Cloudflare Quick Tunnel hosts are cross-site in browsers, however,
# so a demo can opt into ``None`` through the local .env while retaining
# Secure=True above.
JWT_AUTH_COOKIE_SAMESITE = config(
    "JWT_AUTH_COOKIE_SAMESITE",
    default="Lax",
)
CSRF_COOKIE_SAMESITE = config(
    "CSRF_COOKIE_SAMESITE",
    default=JWT_AUTH_COOKIE_SAMESITE,
)
