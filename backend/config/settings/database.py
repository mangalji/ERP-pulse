"""
Database configurations for AGSuite ERP.

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
    "NAME": config(
        "LOCAL_DB_NAME",
        default=str(BASE_DIR / "db.sqlite3"),
    ),
    "OPTIONS": {
        "timeout": 30,
    },
}

# ------------------------------------------------------------
# Test Database
# ------------------------------------------------------------

TEST_DATABASE = {
    "ENGINE": "django.db.backends.sqlite3",
    "NAME": config(
        "LOCAL_DB_NAME",
        default=str(BASE_DIR / "db.sqlite3"),
    ),
    "OPTIONS": {
        "timeout": 30,
    },
}

# ------------------------------------------------------------
# Production Database (Neon)
# ------------------------------------------------------------
# default="" (not a required config()) — this module is imported by
# local.py and testing.py too, which only need LOCAL_DATABASE/
# TEST_DATABASE above. Without a default here, PRODUCTION_DATABASE's
# line still executes on every import (Python runs the whole module
# top-to-bottom regardless of which name the importer actually wants),
# forcing DATABASE_URL to be set even for local development and tests
# that never touch this value. Only production.py actually uses
# PRODUCTION_DATABASE as DATABASES — it's still production.py's job to
# fail loudly if DATABASE_URL is genuinely unset there.


PRODUCTION_DATABASE = dj_database_url.config(
    default=config("DATABASE_URL",default="")
)