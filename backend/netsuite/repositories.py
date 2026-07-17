from accounts.models import User
from netsuite.models import NetSuiteConnection
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