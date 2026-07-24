"""
Database configurations for ERP Pulse.

This module ONLY defines database configurations.

It does NOT decide which environment is active.
That responsibility belongs to:

- local.py
- testing.py
- production.py
"""
from pathlib import Path
import dj_database_url
from decouple import config

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# ------------------------------------------------------------
# Local Development Database
# ------------------------------------------------------------

LOCAL_DATABASE = {
    "ENGINE": "django.db.backends.sqlite3",
    "NAME": config("LOCAL_DB_NAME", default="db.sqlite3"),
}

# ------------------------------------------------------------
# Test Database
# ------------------------------------------------------------

TEST_DATABASE = {
    "ENGINE": "django.db.backends.sqlite3",
    "NAME": config("TEST_DB_NAME", default="test_db.sqlite3"),
}

# ------------------------------------------------------------
# Production Database (Neon)
# ------------------------------------------------------------

PRODUCTION_DATABASE = dj_database_url.config(
    default=config("DATABASE_URL")
)