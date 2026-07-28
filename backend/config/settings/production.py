from .base import *

DEBUG = False

from .database import PRODUCTION_DATABASE

if not PRODUCTION_DATABASE:
    raise RuntimeError(
        'DATABASE_URL is not set. Production requires a real database '
        'connection string — refusing to start rather than silently '
        'falling back to an empty DATABASES config.'
    )

DATABASES = {
    "default": PRODUCTION_DATABASE
}

# ------------------------------------------------------------------
# Production Security Hardening
# These override defaults from base.py/security.py that are safe for
# local dev but insecure for production. Set matching values in your
# Render Dashboard > Environment tab.
# ------------------------------------------------------------------

# Redirect all HTTP to HTTPS
SECURE_SSL_REDIRECT = True

# HSTS: tell browsers to always use HTTPS for this domain
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Secure cookies — only sent over HTTPS
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# Strict referrer policy for production
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
