import uuid

from django.conf import settings
from django.db import models


class NetSuiteConnection(models.Model):
    """
    One row per ERP Pulse user's connected NetSuite account.

    Stores only the OAuth token set for that connection — no NetSuite
    business data (Customers/Items/Sales Orders live in their own models
    in a later task, per NETSUITE_CONTEXT.md). Populated by
    NetSuiteConnectionService after the OAuth callback succeeds
    (see services.py) and refreshed by NetSuiteAuthClient when the
    access token expires.

    SECURITY NOTE: access_token/refresh_token are stored as plaintext
    TextField for this scaffolding step. Encrypting these at rest (e.g.
    via a Fernet-backed field) is recommended before real credentials
    flow through this table in production — intentionally not added here
    to avoid pulling in a new dependency ahead of an actual data-fetching
    task; flagged for follow-up.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='netsuite_connection',
    )

    # Confirmed at connect time and stored per-connection rather than
    # assumed from NETSUITE_ACCOUNT_ID in settings, since that global
    # config could change independently of an already-connected user.
    netsuite_account_id = models.CharField(max_length=50)

    access_token = models.TextField()
    refresh_token = models.TextField()

    access_token_expires_at = models.DateTimeField()
    refresh_token_expires_at = models.DateTimeField(null=True, blank=True)

    is_active = models.BooleanField(default=True)

    connected_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'netsuite_connection'

    def __str__(self) -> str:
        return f'NetSuite connection for {self.user.email}'
