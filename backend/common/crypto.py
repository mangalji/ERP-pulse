"""
Field-level encryption for sensitive values stored at rest.

Used by netsuite.models.NetSuiteConnection for client_secret, access_token,
and refresh_token — see that model's docstring. Encryption/decryption is
transparent at the model layer (EncryptedTextField), so services.py,
client.py, and repositories.py keep reading/writing connection.access_token
etc. as plain strings; nothing outside this file needs to know encryption
is happening.
"""

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.db import models


def _get_fernet() -> Fernet:
    # Resolved lazily (not at import time) so settings are fully loaded
    # first, and so a missing key only breaks code paths that actually
    # touch an encrypted field rather than every import of this module.
    key = settings.FIELD_ENCRYPTION_KEY
    if not key:
        raise ValueError(
            'FIELD_ENCRYPTION_KEY is not set. Generate one with '
            '`python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` '
            'and set it as an environment variable before storing NetSuite credentials.'
        )
    return Fernet(key.encode() if isinstance(key, str) else key)


class EncryptedTextField(models.TextField):
    """
    A TextField that is encrypted with Fernet (AES-128-CBC + HMAC) before
    it reaches the database and decrypted transparently on read.

    Values already in the DB before this field type was introduced are
    plaintext; from_db_value() falls back to returning them as-is if
    Fernet decryption fails, so existing rows don't break on first read.
    Re-saving such a row (e.g. via update_tokens()) re-encrypts it going
    forward.
    """

    def get_prep_value(self, value):
        value = super().get_prep_value(value)
        if value is None or value == '':
            return value
        return _get_fernet().encrypt(value.encode()).decode()

    def from_db_value(self, value, expression, connection):
        if value is None or value == '':
            return value
        try:
            return _get_fernet().decrypt(value.encode()).decode()
        except InvalidToken:
            # Pre-encryption plaintext row — return as-is rather than
            # raising, so migrating existing connections doesn't lock
            # users out. Gets encrypted on the next save.
            return value

    def to_python(self, value):
        return value
