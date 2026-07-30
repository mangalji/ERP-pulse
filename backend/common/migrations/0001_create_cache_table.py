"""
Creates the 'django_cache' table used by CACHES['default'] in
production (config/settings/cache.py, DatabaseCache backend) —
local dev overrides CACHES to LocMemCache (config/settings/local.py)
so it never needs this table, which is why this was easy to miss
before deploying.

Wrapped in a migration — rather than requiring `manage.py
createcachetable` to be run as a separate manual step — so the table
gets created automatically by the normal `manage.py migrate` step
that's already part of every deploy, and can't be forgotten.

Without this table, every call to Django's cache framework in
production raises OperationalError ("no such table: django_cache").
That includes ai/context_builder.py's build_context(), which calls
cache.get()/cache.set() unconditionally on every AI chat request that
falls back to the context-driven pipeline — i.e. this alone was
enough to crash the AI Assistant with a 500 on effectively every
message in production.

Idempotent: checks whether the table already exists before creating
it, since it may already have been created manually against the
production database directly (as happened here) before this migration
was ever committed — without this check, deploying this migration
against a database that already has the table would fail with
"relation already exists" and break the whole `migrate` step.
"""
from django.core.management import call_command
from django.db import migrations

CACHE_TABLE_NAME = "django_cache"


def create_cache_table(apps, schema_editor):
    existing_tables = schema_editor.connection.introspection.table_names()
    if CACHE_TABLE_NAME in existing_tables:
        return
    call_command("createcachetable", CACHE_TABLE_NAME)


def drop_cache_table(apps, schema_editor):
    schema_editor.execute(f"DROP TABLE IF EXISTS {CACHE_TABLE_NAME}")


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.RunPython(create_cache_table, drop_cache_table),
    ]