#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys


def main():

    """Run administrative tasks."""
    # Respect an explicitly configured settings module. Otherwise select
    # local/production from DJANGO_DEBUG or DEBUG.
    if not os.environ.get("DJANGO_SETTINGS_MODULE"):
        debug_value = os.environ.get(
            "DJANGO_DEBUG",
            os.environ.get("DEBUG", "True")
        )
        debug = debug_value.strip().lower() in (
            "true", "1", "yes", "on"
        )
        os.environ.setdefault(
            "DJANGO_SETTINGS_MODULE",
            "config.settings.local" if debug else "config.settings.production",
        )
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        print(f"[manage.py] ImportError when importing Django: {exc}", flush=True)
        print(f"[manage.py] sys.path is: {sys.path}", flush=True)
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
