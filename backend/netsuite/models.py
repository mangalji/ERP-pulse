import uuid

from django.conf import settings
from django.db import models
from common.utils.crypto import EncryptedTextField


class NetSuiteConnection(models.Model):

    ENVIRONMENT_CHOICES = [
        ("sandbox", "Sandbox"),
        ("production", "Production"),
    ]

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("connected", "Connected"),
        ("disconnected", "Disconnected"),
        ("error", "Error"),
    ]


    """
    One row per ERP Pulse user's connected NetSuite account.

    Stores only the OAuth token set for that connection — no NetSuite
    business data (Customers/Items/Sales Orders live in their own models
    in a later task, per NETSUITE_CONTEXT.md). Populated by
    NetSuiteConnectionService after the OAuth callback succeeds
    (see services.py) and refreshed by NetSuiteAuthClient when the
    access token expires.

    SECURITY NOTE: client_secret/access_token/refresh_token are encrypted
    at rest via EncryptedTextField (Fernet). FIELD_ENCRYPTION_KEY must be
    set in the environment before any connection is created — see
    common/utils/crypto.py.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # user = models.OneToOneField(
    #     settings.AUTH_USER_MODEL,
    #     on_delete=models.CASCADE,
    #     related_name='netsuite_connection',
    # )

    user = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name="netsuite_connections")

    client_name = models.CharField(max_length=255,null=True,blank=True)
    # Confirmed at connect time and stored per-connection rather than
    # assumed from NETSUITE_ACCOUNT_ID in settings, since that global
    # config could change independently of an already-connected user.

    environment = models.CharField(
        max_length=20,
        choices=ENVIRONMENT_CHOICES,
        null=True,
        blank=True,
    )
    client_id = models.CharField(max_length=255,null=True,blank=True)

    # client_secret = models.TextField(null=True,blank=True)
    client_secret = EncryptedTextField(null=True,blank=True)
    netsuite_account_id = models.CharField(max_length=50)

    access_token = EncryptedTextField(null=True,blank=True)
    refresh_token = EncryptedTextField(null=True,blank=True)

    access_token_expires_at = models.DateTimeField(null=True,blank=True)
    refresh_token_expires_at = models.DateTimeField(null=True, blank=True)
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending",
    )
    is_active = models.BooleanField(default=False)

    connected_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'netsuite_connection'

        constraints = [
            models.UniqueConstraint(
                fields=["user", "netsuite_account_id"],
                name="unique_user_netsuite_account",
            )
        ]


    def __str__(self):
        return f"{self.client_name} ({self.user.email})"
