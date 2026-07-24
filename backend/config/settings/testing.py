from .base import *

DEBUG = False

from .database import TEST_DATABASE

DATABASES = {
    "default": TEST_DATABASE
}

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"