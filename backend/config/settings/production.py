from .base import *

DEBUG = False

from .database import PRODUCTION_DATABASE

if not PRODUCTION_DATABASE:
    raise RuntimeError(
        'DATABASE_URL is not set. Production requires a real database '
        'connection string — refusing to start rather than silently '
        'falling back to an empty DATABASES config.'
    )

DATABASES = {
    "default": PRODUCTION_DATABASE
}
