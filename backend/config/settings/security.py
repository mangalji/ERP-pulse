"""
Security settings for AGSuite ERP.
"""

from decouple import Csv, config

# ------------------------------------------------------------------
# Browser Security
# ------------------------------------------------------------------

SECURE_BROWSER_XSS_FILTER = config(
    "SECURE_BROWSER_XSS_FILTER",
    default=True,
    cast=bool,
)

SECURE_CONTENT_TYPE_NOSNIFF = config(
    "SECURE_CONTENT_TYPE_NOSNIFF",
    default=True,
    cast=bool,
)

SECURE_REFERRER_POLICY = config(
    "SECURE_REFERRER_POLICY",
    default="strict-origin-when-cross-origin",
)

X_FRAME_OPTIONS = config(
    "X_FRAME_OPTIONS",
    default="DENY",
)

# ------------------------------------------------------------------
# Reverse Proxy (Render / Nginx)
# ------------------------------------------------------------------

SECURE_PROXY_SSL_HEADER = (
    "HTTP_X_FORWARDED_PROTO",
    "https",
)

# ------------------------------------------------------------------
# HSTS
# ------------------------------------------------------------------

# DEBUG is not yet defined at import time (security.py is imported by
# base.py before base.py reads DEBUG from config), so we read it from
# the env directly — safe default is 0 (disabled) to match local-dev
# expectations; production.py overrides to 1 year.
SECURE_HSTS_SECONDS = config(
    "SECURE_HSTS_SECONDS",
    default=0,
    cast=int,
)

SECURE_HSTS_INCLUDE_SUBDOMAINS = config(
    "SECURE_HSTS_INCLUDE_SUBDOMAINS",
    default=True,
    cast=bool,
)

SECURE_HSTS_PRELOAD = config(
    "SECURE_HSTS_PRELOAD",
    default=True,
    cast=bool,
)

# ------------------------------------------------------------------
# Upload Limits
# ------------------------------------------------------------------

DATA_UPLOAD_MAX_MEMORY_SIZE = config(
    "DATA_UPLOAD_MAX_MEMORY_SIZE",
    default=2621440,
    cast=int,
)

DATA_UPLOAD_MAX_NUMBER_FIELDS = config(
    "DATA_UPLOAD_MAX_NUMBER_FIELDS",
    default=1000,
    cast=int,
)

# ------------------------------------------------------------------
# Secure Cookies
# ------------------------------------------------------------------

SESSION_COOKIE_SECURE = config(
    "SESSION_COOKIE_SECURE",
    default=False,
    cast=bool,
)

CSRF_COOKIE_SECURE = config(
    "CSRF_COOKIE_SECURE",
    default=False,
    cast=bool,
)

# ------------------------------------------------------------------
# CSRF
# ------------------------------------------------------------------

CSRF_TRUSTED_ORIGINS = config(
    "CSRF_TRUSTED_ORIGINS",
    default="http://localhost:5173,http://localhost:8000",
    cast=Csv(),
)

# ------------------------------------------------------------------
# CORS
# ------------------------------------------------------------------

CORS_ALLOWED_ORIGINS = config(
    "CORS_ALLOWED_ORIGINS",
    default="http://localhost:5173",
    cast=Csv(),
)

# Required for httpOnly cookie-based JWT auth -- without this, the browser
# won't attach the access_token/refresh_token cookies on cross-origin
# requests (e.g. frontend on port 5173 calling backend on port 8000).
CORS_ALLOW_CREDENTIALS = True

# ------------------------------------------------------------------
# Frontend URL
# ------------------------------------------------------------------

FRONTEND_URL = config(
    "FRONTEND_URL",
    default="http://localhost:5173",
)