"""
Application definitions for ERP Pulse.

This module keeps application registration isolated from the rest of the
settings so base.py remains clean and easy to read.
"""

DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
]

LOCAL_APPS = [
    "common",
    "accounts",
    "netsuite",
    "ai",
    "dashboard",
    "reports",
    "monitoring",
    "sync",
    "analytics",
]

INSTALLED_APPS = (
    DJANGO_APPS
    + THIRD_PARTY_APPS
    + LOCAL_APPS
)