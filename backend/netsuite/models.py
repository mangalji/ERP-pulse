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
    user = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name="netsuite_connections")
    client_name = models.CharField(max_length=255,null=True,blank=True)
    environment = models.CharField(
        max_length=20,
        choices=ENVIRONMENT_CHOICES,
        null=True,
        blank=True,
    )
    client_id = models.CharField(max_length=255,null=True,blank=True)
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
    last_synced_at = models.DateTimeField(null=True, blank=True)
    last_used_at = models.DateTimeField(
        null=True, blank=True,
        help_text='Last time any live NetSuite API call succeeded through this '
                   'connection — broader than last_synced_at, which is scoped to '
                   'sync jobs specifically.',
    )
    last_error = models.TextField(null=True, blank=True)
    consecutive_failures = models.PositiveIntegerField(default=0)
    connected_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Failure streak beyond which a "connected" connection is reported as
    # unhealthy rather than healthy — chosen to tolerate a couple of
    # transient blips without flapping the status, while still surfacing
    # a connection that's genuinely stuck failing.
    UNHEALTHY_FAILURE_THRESHOLD = 3

    class Meta:
        db_table = 'netsuite_connection'

        constraints = [
            models.UniqueConstraint(
                fields=["user", "netsuite_account_id"],
                name="unique_user_netsuite_account",
            )
        ]

    @property
    def health(self) -> str:
        """
        Computed, not stored — derived from status + consecutive_failures
        so there's one source of truth instead of two fields that could
        drift out of sync with each other.

        One of: 'healthy', 'degraded', 'unhealthy', 'disconnected'.
        """
        if self.status in ('disconnected', 'pending'):
            return 'disconnected'
        if self.status == 'error' or self.consecutive_failures >= self.UNHEALTHY_FAILURE_THRESHOLD:
            return 'unhealthy'
        if self.consecutive_failures > 0:
            return 'degraded'
        return 'healthy'


    def __str__(self):
        return f"{self.client_name} ({self.user.email})"


class NetSuiteConnectionAuditLog(models.Model):
    """
    One row per lifecycle event on a NetSuiteConnection — created,
    renamed, deleted, switched active, OAuth completed, or a sync
    failure recorded against it.

    `connection` is nullable and SET_NULL on delete (not CASCADE) so a
    deleted connection's audit history survives the deletion itself —
    otherwise "this connection was deleted" would delete its own audit
    trail as a side effect, which defeats the point of an audit log.
    `netsuite_account_id`/`client_name` are duplicated onto the log row
    (not just looked up via the FK) for the same reason: they need to
    stay readable after the connection is gone.
    """

    ACTION_CHOICES = [
        ('created', 'Created'),
        ('oauth_completed', 'OAuth Completed'),
        ('renamed', 'Renamed'),
        ('switched_active', 'Switched Active'),
        ('deleted', 'Deleted'),
        ('sync_failed', 'Sync Failed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    connection = models.ForeignKey(
        NetSuiteConnection,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='audit_logs',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='netsuite_connection_audit_logs',
    )

    action = models.CharField(max_length=30, choices=ACTION_CHOICES)
    netsuite_account_id = models.CharField(max_length=50, null=True, blank=True)
    client_name = models.CharField(max_length=255, null=True, blank=True)
    detail = models.TextField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'netsuite_connection_audit_log'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at'], name='ns_audit_user_recent_idx'),
        ]

    def __str__(self):
        return f'{self.get_action_display()} — {self.client_name or self.netsuite_account_id}'
