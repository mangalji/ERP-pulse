"""
Base settings for ERP Pulse.

This file contains settings shared by every environment:
- Local Development
- Testing
- Production

Environment-specific settings should never be added here.
"""

from pathlib import Path
from decouple import Csv, config
from .apps import INSTALLED_APPS
# from .database import *
from .email import *
from .jwt import *
from .rest_framework import *
from .security import *
from .logging import *
from .cache import *
from .ocr import *


# ------------------------------------------------------------------
# Paths
# ------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# ------------------------------------------------------------------
# Core
# ------------------------------------------------------------------

SECRET_KEY = config("SECRET_KEY")

DEBUG = config(
    "DEBUG",
    default=False,
    cast=bool,
)

ALLOWED_HOSTS = config(
    "ALLOWED_HOSTS",
    default="localhost,127.0.0.1",
    cast=Csv(),
)

# ------------------------------------------------------------------
# Installed Applications
# ------------------------------------------------------------------

INSTALLED_APPS = INSTALLED_APPS

# ------------------------------------------------------------------
# Middleware
# ------------------------------------------------------------------

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",

    "whitenoise.middleware.WhiteNoiseMiddleware",

    "corsheaders.middleware.CorsMiddleware",

    "django.contrib.sessions.middleware.SessionMiddleware",

    "django.middleware.common.CommonMiddleware",

    "django.middleware.csrf.CsrfViewMiddleware",

    "django.contrib.auth.middleware.AuthenticationMiddleware",

    "tenancy.middleware.TenantMiddleware",

    "django.contrib.messages.middleware.MessageMiddleware",

    "django.middleware.clickjacking.XFrameOptionsMiddleware",

    "monitoring.middlewares.RequestMonitoringMiddleware",
]



# ------------------------------------------------------------------
# URL Configuration
# ------------------------------------------------------------------

ROOT_URLCONF = "config.urls"

# ------------------------------------------------------------------
# Templates
# ------------------------------------------------------------------

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",

        "DIRS": [],

        "APP_DIRS": True,

        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",

                "django.contrib.auth.context_processors.auth",

                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]


# ------------------------------------------------------------------
# WSGI / ASGI
# ------------------------------------------------------------------

WSGI_APPLICATION = "config.wsgi.application"

ASGI_APPLICATION = "config.asgi.application"


# ------------------------------------------------------------------
# User Model
# ------------------------------------------------------------------

AUTH_USER_MODEL = "accounts.User"


# ------------------------------------------------------------------
# Password Validators
# ------------------------------------------------------------------

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS":{
            "min_length":8,
        }
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
    {
        "NAME": "accounts.validators.StrongPasswordValidator",
    },
]

# ------------------------------------------------------------------
# Internationalization
# ------------------------------------------------------------------

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True


# ------------------------------------------------------------------
# Static Files
# ------------------------------------------------------------------

STATIC_URL = "static/"

STATIC_ROOT = BASE_DIR / "staticfiles"

STATICFILES_STORAGE = (
    "whitenoise.storage.CompressedManifestStaticFilesStorage"
)

MEDIA_URL = "media/"

MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AI_PROVIDER = config("AI_PROVIDER", default="gemini")

GEMINI_API_KEY = config("GEMINI_API_KEY", default="")

GEMINI_MODEL = config(
    "GEMINI_MODEL",
    default="gemini-2.5-flash",
)

OPENAI_API_KEY = config(
    "OPENAI_API_KEY",
    default="",
)

OPENAI_MODEL = config(
    "OPENAI_MODEL",
    default="gpt-4o-mini",
)

NETSUITE_REDIRECT_URI = config(
    "NETSUITE_REDIRECT_URI",
    default="",
)

FIELD_ENCRYPTION_KEY = config(
    "FIELD_ENCRYPTION_KEY",
    default="",
)

if DEBUG:
    TEMPLATES[0]["OPTIONS"]["debug"] = True

# ------------------------------------------------------------------
# Celery
# ------------------------------------------------------------------

CELERY_BROKER_URL = config("CELERY_BROKER_URL", default="redis://127.0.0.1:6379/0")
CELERY_RESULT_BACKEND = config("CELERY_RESULT_BACKEND", default="redis://127.0.0.1:6379/0")
celery_broker_url = CELERY_BROKER_URL
celery_result_backend = CELERY_RESULT_BACKEND
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60  # 30 minutes
