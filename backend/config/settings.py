"""
Django settings for the ERP Pulse project.

MVP note: a single settings file is used intentionally (no base/development
split) to keep the project simple for a 6-day MVP timeline, per project
decision. All environment-specific and sensitive values are read from
environment variables — never hardcoded — per BACKEND_CONTEXT.md and
NETSUITE_CONTEXT.md security rules.
"""

from datetime import timedelta
from pathlib import Path
import dj_database_url
import os

from decouple import Csv, config

BASE_DIR = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------

SECRET_KEY = config('SECRET_KEY')
DEBUG = config('DEBUG', default=False, cast=bool)
ALLOWED_HOSTS = config(
    'ALLOWED_HOSTS',
    default='localhost,127.0.0.1',
    cast=Csv(),
)

# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------

DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

THIRD_PARTY_APPS = [
    'rest_framework',
    'rest_framework_simplejwt',
    "rest_framework_simplejwt.token_blacklist",
    'corsheaders',
]

LOCAL_APPS = [
    'common',
    'accounts',
    'netsuite',
    'ai',
    'dashboard',
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'corsheaders.middleware.CorsMiddleware',  # must sit above CommonMiddleware
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


# ---------------------------------------------------------------------------
# Database (PostgreSQL only — ADR-003, DATABASE_CONTEXT.md)
# ---------------------------------------------------------------------------

DATABASES = {
    "default": dj_database_url.config(
        default=config("DATABASE_URL")
    )
}

# ---------------------------------------------------------------------------
# Custom User Model
# ---------------------------------------------------------------------------
# Required because email (not username) is the login identifier —
# AUTHENTICATION_DESIGN.md, Section 3. Must be set before the first
# migration touching auth is applied.

AUTH_USER_MODEL = 'accounts.User'


# ---------------------------------------------------------------------------
# Password validation
# ---------------------------------------------------------------------------

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# ---------------------------------------------------------------------------
# Internationalization
# ---------------------------------------------------------------------------

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True


# ---------------------------------------------------------------------------
# Static files
# ---------------------------------------------------------------------------

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / "staticfiles"

STATICFILES_STORAGE = (
    "whitenoise.storage.CompressedManifestStaticFilesStorage"
)

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# for Email Services
# EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
if config('EMAIL_HOST',default=''):
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST = config('EMAIL_HOST')
    EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
    EMAIL_HOST_USER = config('EMAIL_HOST_USER')
    EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD')
    EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
else:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='noreply@erppulse.local')


# ---------------------------------------------------------------------------
# Django REST Framework
# ---------------------------------------------------------------------------
# Minimal configuration only. The standard {success, message, data} response
# envelope (custom renderer/exception handler) is intentionally deferred to
# when real API endpoints are built, per approved Day 1 scope.

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'EXCEPTION_HANDLER':'common.exception_handler.standard_exception_handler',
    'DEFAULT_THROTTLE_CLASSES': (
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ),
    'DEFAULT_THROTTLE_RATES': {
        'anon': config('THROTTLE_ANON', default='100/min'),
        'user': config('THROTTLE_USER', default='1000/min'),
        'login_otp': config('THROTTLE_LOGIN_OTP', default='5/min'),
        'register_otp': config('THROTTLE_REGISTER_OTP', default='5/min'),
        'ai_chat': config('THROTTLE_AI_CHAT', default='20/min'),
        'dashboard': config('THROTTLE_DASHBOARD', default='120/min'),
        'netsuite_sync': config('THROTTLE_NETSUITE_SYNC', default='30/min'),
    },
}


# ---------------------------------------------------------------------------
# JWT (SimpleJWT)
# ---------------------------------------------------------------------------
# Login/Register/Refresh endpoints are Day 2 scope. Only framework-level
# configuration happens on Day 1 so Day 2 can add endpoints without touching
# settings again.

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(
        minutes=config('JWT_ACCESS_TOKEN_LIFETIME_MINUTES', default=15, cast=int)
    ),
    'REFRESH_TOKEN_LIFETIME': timedelta(
        days=config('JWT_REFRESH_TOKEN_LIFETIME_DAYS', default=7, cast=int)
    ),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
}


# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
# Explicit allow-list only — never wildcarded — so the React dev server can
# reach the API while unknown origins remain blocked by default.

CORS_ALLOWED_ORIGINS = config(
    'CORS_ALLOWED_ORIGINS',
    default='http://localhost:5173',
    cast=Csv(),
)

# ---------------------------------------------------------------------------
# Frontend
# ---------------------------------------------------------------------------
# Used only to build redirect targets from server-side views that a human
# browser lands on directly (e.g. the NetSuite OAuth callback) — not used
# for CORS, which is governed by CORS_ALLOWED_ORIGINS above.

FRONTEND_URL = config('FRONTEND_URL', default='http://localhost:5173')


# ---------------------------------------------------------------------------
# NetSuite OAuth 2.0 (ADR-007 — dedicated netsuite module; NETSUITE_CONTEXT.md)
# ---------------------------------------------------------------------------
# Real credentials don't exist yet, so every value defaults to '' rather
# than being required — this keeps `manage.py check`/`runserver` working
# today. netsuite/oauth.py and netsuite/client.py each validate that these
# are actually set before attempting to use them, and raise
# NetSuiteConfigurationException (not a raw crash) if they aren't.
# Never hardcode these values — NETSUITE_CONTEXT.md "Authentication"
# section.

# NETSUITE_ACCOUNT_ID = config('NETSUITE_ACCOUNT_ID', default='')
# NETSUITE_CLIENT_ID = config('NETSUITE_CLIENT_ID', default='')
# NETSUITE_CLIENT_SECRET = config('NETSUITE_CLIENT_SECRET', default='')
NETSUITE_REDIRECT_URI = config('NETSUITE_REDIRECT_URI', default='')

# ---------------------------------------------------------------------------
# Field-level encryption (common/utils/crypto.py — EncryptedTextField)
# ---------------------------------------------------------------------------
# Encrypts NetSuiteConnection.client_secret/access_token/refresh_token at
# rest. Defaults to '' like the NETSUITE_* block above (keeps `manage.py
# check`/`runserver` working without it) — EncryptedTextField itself raises
# a clear error if a value is actually read/written while unset, rather
# than silently storing plaintext. MUST be set to a real Fernet key
# (`Fernet.generate_key()`) before any real NetSuite credentials are
# stored, and must stay stable across deploys — rotating it makes
# previously-encrypted rows unreadable.

FIELD_ENCRYPTION_KEY = config('FIELD_ENCRYPTION_KEY', default='')




# ---------------------------------------------------------------------------
# AI Provider (ADR-010 — provider abstraction; AI_CONTEXT.md)
# ---------------------------------------------------------------------------
# Same philosophy as the NetSuite section above: OPENAI_API_KEY defaults to
# '' rather than being required, so `manage.py check`/`runserver` keep
# working without it. ai/providers.py validates this is set before calling
# OpenAI and raises AIProviderNotConfiguredException (not a raw crash) if
# it isn't.

AI_PROVIDER = config("AI_PROVIDER", default="gemini")
GEMINI_API_KEY = config("GEMINI_API_KEY", default="")
GEMINI_MODEL = config("GEMINI_MODEL", default="gemini-2.5-flash")
OPENAI_API_KEY = config("OPENAI_API_KEY", default="")
OPENAI_MODEL = config("OPENAI_MODEL", default="gpt-4o-mini")


# ---------------------------------------------------------------------------
# Security Hardening
# ---------------------------------------------------------------------------
# All security flags are driven by environment variables so the same
# settings file works in development and production without code changes.

SECURE_BROWSER_XSS_FILTER = config('SECURE_BROWSER_XSS_FILTER', default=True, cast=bool)
SECURE_CONTENT_TYPE_NOSNIFF = config('SECURE_CONTENT_TYPE_NOSNIFF', default=True, cast=bool)
SECURE_REFERRER_POLICY = config('SECURE_REFERRER_POLICY', default='strict-origin-when-cross-origin')
X_FRAME_OPTIONS = config('X_FRAME_OPTIONS', default='DENY')

# Session and CSRF cookies are marked Secure in production so browsers
# never send them over plain HTTP. In development (DEBUG=True) this can
# be relaxed via the env var.
SESSION_COOKIE_SECURE = config('SESSION_COOKIE_SECURE', default=False, cast=bool)
CSRF_COOKIE_SECURE = config('CSRF_COOKIE_SECURE', default=False, cast=bool)

# Trusted origins for CSRF checks. Defaults to the frontend dev server
# plus localhost API origins. Must be set explicitly in production.
CSRF_TRUSTED_ORIGINS = config(
    'CSRF_TRUSTED_ORIGINS',
    default='http://localhost:5173,http://localhost:8000',
    cast=Csv(),
)

# ---------------------------------------------------------------------------
# DEBUG safeguards
# ---------------------------------------------------------------------------
# When DEBUG is True, these extra flags ensure debug information is not
# inadvertently exposed in production-like environments.

if DEBUG:
    # Ensure template debug mirrors DEBUG rather than being left on
    # accidentally in production.
    TEMPLATES[0]['OPTIONS']['debug'] = True
