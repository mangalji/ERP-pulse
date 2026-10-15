from .base import *
import os
import dj_database_url
from django.core.exceptions import ImproperlyConfigured

DEBUG = False
test_url = os.environ.get('TEST_DATABASE_URL', '')
if not test_url:
    raise ImproperlyConfigured('Set TEST_DATABASE_URL to a dedicated PostgreSQL test server.')
test_db = dj_database_url.parse(test_url, conn_max_age=0)
if test_db['ENGINE'] != 'django.db.backends.postgresql':
    raise ImproperlyConfigured('The migration suite requires PostgreSQL.')
test_name = os.environ.get('TEST_DATABASE_NAME', 'test_agsuite')
if not test_name.startswith('test_') or test_name == test_db['NAME']:
    raise ImproperlyConfigured('Use a separate test database name starting with test_.')
test_db['TEST'] = {'NAME': test_name}
DATABASES = {'default': test_db}
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
CACHES = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}
SECURE_SSL_REDIRECT = False
