#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import env_setup  # Automatically resolves site-packages & installs dependencies on Catalyst if needed
import os
import sys


def main():
    # """Run administrative tasks."""
    # debug = os.environ.get("DJANGO_DEBUG","True") in ("True","1","yes","on")
    # os.environ.setdefault(
    #     'DJANGO_SETTINGS_MODULE', 
    #     'config.settings.local' if debug else "config.settings.production",
    #     )
    """Run administrative tasks."""
    # Respect an explicitly configured settings module (e.g. Catalyst).
    # Otherwise select local/production from DJANGO_DEBUG or DEBUG.
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
    # Dynamically bind to X_ZOHO_CATALYST_LISTEN_PORT if provided by Catalyst
    catalyst_port = os.environ.get("X_ZOHO_CATALYST_LISTEN_PORT")
    if catalyst_port and len(sys.argv) > 1 and sys.argv[1] == "runserver":
        print(f"[manage.py] Overriding runserver port with Catalyst listen port: {catalyst_port}", flush=True)
        # Rebuild sys.argv with 0.0.0.0:<catalyst_port>
        new_argv = [sys.argv[0], "runserver"]
        for arg in sys.argv[2:]:
            if ":" in arg or arg.isdigit():
                continue
            new_argv.append(arg)
        new_argv.append(f"0.0.0.0:{catalyst_port}")
        sys.argv = new_argv

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
