"""
Cache configuration for ERP Pulse.

Bug fix context: without an explicit CACHES setting, Django silently
falls back to LocMemCache — an in-memory cache local to a single
Python process. accounts/registration_cache.py stores the entire
in-flight registration (email, hashed password, OTP hash, attempt
count) via Django's cache framework, so with LocMemCache that state
does not survive across gunicorn worker processes or across multiple
server instances in production. A Register request handled by one
worker and a Verify OTP request handled by another worker see two
completely separate caches, so the second request fails with
"No registration in progress for this email." — intermittently,
depending purely on which worker picks up which request.

Fix: use Django's built-in database-backed cache instead. It's shared
by every worker/instance because they all already talk to the same
Postgres database — no new infrastructure (Redis) required, matching
the project's existing "DB-native over new infra" approach used
elsewhere (see netsuite/token_manager.py). The backing table is
created by common/migrations/0001_create_cache_table.py.
"""

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "django_cache",
    }
}