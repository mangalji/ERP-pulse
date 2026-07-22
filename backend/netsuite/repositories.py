from accounts.models import User
from netsuite.models import NetSuiteConnection, NetSuiteConnectionAuditLog
from django.db import transaction


class NetSuiteConnectionRepository:
    """
    Persistence-only operations for NetSuiteConnection.

    Contains no OAuth/HTTP logic — token exchange happens in
    NetSuiteAuthClient (client.py), orchestration in
    NetSuiteConnectionService (services.py). This class only reads from
    and writes to the database.
    """

    def get_by_user(self, user: User) -> NetSuiteConnection | None:
        return NetSuiteConnection.objects.filter(user=user,is_active=True).first()

    def update_tokens(
        self,
        connection: NetSuiteConnection,
        *,
        access_token: str,
        refresh_token: str,
        access_token_expires_at,
        refresh_token_expires_at=None,
    ) -> NetSuiteConnection:
        """Persist a refreshed access/refresh token pair after a token-refresh call."""
        connection.access_token = access_token
        connection.refresh_token = refresh_token
        connection.access_token_expires_at = access_token_expires_at
        if refresh_token_expires_at is not None:
            connection.refresh_token_expires_at=refresh_token_expires_at
        connection.status = "connected"
        connection.save(
            update_fields=[
                'access_token', 'refresh_token', 'access_token_expires_at','refresh_token_expires_at','status', 'updated_at',
            ]
        )
        return connection

    def deactivate(self, connection: NetSuiteConnection) -> NetSuiteConnection:
        """Mark a connection inactive (e.g. on disconnect) without deleting history."""
        connection.is_active = False
        connection.save(update_fields=['is_active', 'updated_at'])
        return connection

    def list_by_user(self,user:User):
        return NetSuiteConnection.objects.filter(user=user).order_by("-is_active","-connected_at")
    
    def get_by_id(self,user:User,connection_id)-> NetSuiteConnection | None:
        return NetSuiteConnection.objects.filter(
            user=user,
            id=connection_id,
        ).first()
    
    def get_locked(self, connection_id) -> NetSuiteConnection:
        """
        Re-fetch a connection with a Postgres row-level lock (SELECT ...
        FOR UPDATE). Must be called inside `transaction.atomic()`.

        Used by NetSuiteTokenManager to serialize concurrent token
        refreshes for the same connection — without this, two requests
        arriving while the token is expired could both call NetSuite's
        refresh endpoint at once, and since NetSuite rotates refresh
        tokens on use, the second call can fail or the two DB writes can
        race. The lock makes the second caller wait for the first to
        finish and commit before it re-checks expiry.
        """
        return NetSuiteConnection.objects.select_for_update().get(id=connection_id)

    def switch_active_connection(self, user: User, connection: NetSuiteConnection):
        with transaction.atomic():
            NetSuiteConnection.objects.filter(
                user=user,
                is_active=True,
            ).update(is_active=False)

            connection.is_active = True
            connection.save(update_fields=["is_active", "updated_at"])

            return connection
    
    def create(
    self,
    *,
    user:User,
    client_name: str,
    environment: str,
    client_id: str,
    client_secret: str,
    netsuite_account_id: str,
):
        return NetSuiteConnection.objects.create(
        user=user,
        client_name=client_name,
        environment=environment,
        client_id=client_id,
        client_secret=client_secret,
        netsuite_account_id=netsuite_account_id,
        status="pending",
        is_active=False,
    )

    def rename(
    self,
    connection: NetSuiteConnection,
    client_name: str,) -> NetSuiteConnection:
        connection.client_name = client_name
        connection.save(update_fields=["client_name", "updated_at"])
        return connection

    def delete(self, connection: NetSuiteConnection):
        with transaction.atomic():

            user = connection.user
            was_active = connection.is_active

            connection.delete()

            if was_active:
                next_connection = (
                    NetSuiteConnection.objects.filter(
                        user=user,
                        status="connected",
                    )
                    .order_by("-connected_at")
                    .first()
                )

                if next_connection:
                    next_connection.is_active = True
                    next_connection.save(update_fields=["is_active", "updated_at"])

    def record_sync_success(self, connection: NetSuiteConnection) -> NetSuiteConnection:
        """Called after a successful NetSuite data fetch or token refresh."""
        from django.utils import timezone

        connection.last_synced_at = timezone.now()
        connection.last_error = None
        connection.consecutive_failures = 0
        connection.save(
            update_fields=['last_synced_at', 'last_error', 'consecutive_failures', 'updated_at']
        )
        return connection

    def record_sync_failure(self, connection: NetSuiteConnection, *, error_message: str) -> NetSuiteConnection:
        """Called when a NetSuite data fetch or token refresh fails."""
        connection.last_error = error_message[:2000]
        connection.consecutive_failures += 1
        update_fields = ['last_error', 'consecutive_failures', 'updated_at']
        # Three or more failures in a row means this connection needs
        # attention — surface it in the connection list rather than
        # continuing to show a stale "connected" status.
        if connection.consecutive_failures >= NetSuiteConnection.UNHEALTHY_FAILURE_THRESHOLD and connection.status == 'connected':
            connection.status = 'error'
            update_fields.append('status')
        connection.save(update_fields=update_fields)
        return connection

    def touch_last_used(self, connection: NetSuiteConnection) -> NetSuiteConnection:
        """
        Called after any successful live NetSuite API call through this
        connection (record fetch, SuiteQL, token refresh) — broader than
        record_sync_success, which is reserved for actual sync-job runs.
        """
        from django.utils import timezone

        connection.last_used_at = timezone.now()
        connection.save(update_fields=['last_used_at', 'updated_at'])
        return connection

    def complete_OAuth(self,
                       connection:NetSuiteConnection,
                       *,
                       access_token: str,
                       refresh_token: str,
                       access_token_expires_at,
                       refresh_token_expires_at=None):
        with transaction.atomic():
            NetSuiteConnection.objects.filter(
                user=connection.user,
                is_active=True,
            ).exclude(id=connection.id).update(is_active=False)
            connection.access_token=access_token
            connection.refresh_token=refresh_token
            connection.access_token_expires_at = access_token_expires_at
            connection.refresh_token_expires_at = refresh_token_expires_at
            connection.status = "connected"
            connection.is_active = True

            connection.save(
                update_fields=[
                "access_token",
                "refresh_token",
                "access_token_expires_at",
                "refresh_token_expires_at",
                "status",
                "is_active",
                "updated_at",
                ]
            )

            return connection

class NetSuiteConnectionAuditLogRepository:
    """
    Persistence-only operations for NetSuiteConnectionAuditLog.

    Deliberately minimal — a single log() method, since every write is
    the same shape (action + who + which connection + optional detail).
    No update/delete methods: audit rows are append-only by design.
    """

    def log(
        self,
        *,
        action: str,
        connection: NetSuiteConnection | None = None,
        user: User | None = None,
        netsuite_account_id: str | None = None,
        client_name: str | None = None,
        detail: str | None = None,
    ) -> NetSuiteConnectionAuditLog:
        return NetSuiteConnectionAuditLog.objects.create(
            action=action,
            connection=connection,
            user=user or (connection.user if connection else None),
            netsuite_account_id=netsuite_account_id or (connection.netsuite_account_id if connection else None),
            client_name=client_name if client_name is not None else (connection.client_name if connection else None),
            detail=detail,
        )

    def list_by_user(self, user: User, *, limit: int = 100):
        return NetSuiteConnectionAuditLog.objects.filter(user=user)[:limit]
