from .base import *

DEBUG = True

from .database import LOCAL_DATABASE

DATABASES = {
    "default": LOCAL_DATABASE
}

TEMPLATES[0]["OPTIONS"]["debug"] = True

INTERNAL_IPS = [
    "127.0.0.1",
]

# Local development cache
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "erp-pulse-local-cache",
    }
}