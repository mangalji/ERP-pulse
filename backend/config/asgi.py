"""
ASGI config for config project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application

# os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.local')

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
application = get_asgi_application()
