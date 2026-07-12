from accounts.models import User
from netsuite.models import NetSuiteConnection


class NetSuiteConnectionRepository:
    """
    Persistence-only operations for NetSuiteConnection.

    Contains no OAuth/HTTP logic — token exchange happens in
    NetSuiteAuthClient (client.py), orchestration in
    NetSuiteConnectionService (services.py). This class only reads from
    and writes to the database.
    """

    def get_by_user(self, user: User) -> NetSuiteConnection | None:
        return NetSuiteConnection.objects.filter(user=user).first()

    def upsert(
        self,
        *,
        user: User,
        netsuite_account_id: str,
        access_token: str,
        refresh_token: str,
        access_token_expires_at,
        refresh_token_expires_at=None,
    ) -> NetSuiteConnection:
        """
        Create or replace the single connection row for this user. A user
        has at most one active NetSuite connection at a time
        (OneToOneField), so reconnecting overwrites the previous tokens
        rather than creating a duplicate row.
        """
        connection, _ = NetSuiteConnection.objects.update_or_create(
            user=user,
            defaults={
                'netsuite_account_id': netsuite_account_id,
                'access_token': access_token,
                'refresh_token': refresh_token,
                'access_token_expires_at': access_token_expires_at,
                'refresh_token_expires_at': refresh_token_expires_at,
                'is_active': True,
            },
        )
        return connection

    def update_tokens(
        self,
        connection: NetSuiteConnection,
        *,
        access_token: str,
        refresh_token: str,
        access_token_expires_at,
    ) -> NetSuiteConnection:
        """Persist a refreshed access/refresh token pair after a token-refresh call."""
        connection.access_token = access_token
        connection.refresh_token = refresh_token
        connection.access_token_expires_at = access_token_expires_at
        connection.save(
            update_fields=[
                'access_token', 'refresh_token', 'access_token_expires_at', 'updated_at',
            ]
        )
        return connection

    def deactivate(self, connection: NetSuiteConnection) -> NetSuiteConnection:
        """Mark a connection inactive (e.g. on disconnect) without deleting history."""
        connection.is_active = False
        connection.save(update_fields=['is_active', 'updated_at'])
        return connection
