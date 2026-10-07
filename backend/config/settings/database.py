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

LOCAL_DATABASE = dj_database_url.config(
    default=config("LOCAL_DATABASE_URL", default="")
)

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
# Production Database (Supabase PostgreSQL)
# ------------------------------------------------------------

PRODUCTION_DATABASE = dj_database_url.config(
    default=config("DATABASE_URL",default=""),
    # Keep each worker's DB connection open between requests. With the
    # default (0) every request opens a brand-new TCP+TLS+auth connection
    # to the remote database, which is slow on a cross-network hop.
    conn_max_age=600,
    # Verify a reused connection is still alive before using it.
    conn_health_checks=True,
    # Safe with Supabase's PgBouncer pooler; only affects .iterator().
    disable_server_side_cursors=True,
)