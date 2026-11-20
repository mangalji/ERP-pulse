"""WSGI config for the AGSuite ERP project."""

import os
from django.core.wsgi import get_wsgi_application

debug = os.environ.get("DJANGO_DEBUG", os.environ.get("DEBUG", "False")).lower() in ("true", "1", "yes", "on")
default_settings = "config.settings.local" if debug else "config.settings.production"
os.environ.setdefault("DJANGO_SETTINGS_MODULE", default_settings)

application = get_wsgi_application()
