"""
Business logic for connecting an ERP Pulse user's NetSuite account.

Orchestrates oauth.py (URL/state), NetSuiteAuthClient (token exchange),
and NetSuiteConnectionRepository (persistence) — the view layer never
touches any of those directly, mirroring how AuthenticationService
orchestrates UserRepository/OTPService for the accounts app.
"""

import logging
from datetime import timedelta

from django.utils import timezone
from accounts.models import User
from netsuite.client import NetSuiteAuthClient
from netsuite.constants import NetSuiteRecordType
from netsuite.exceptions import NetSuiteStateMismatchException, NetSuiteConnectionNotFoundException
from netsuite.oauth import build_authorization_url, resolve_user_id_from_state
from netsuite.repositories import NetSuiteConnectionRepository

logger = logging.getLogger(__name__)

# Refresh proactively slightly before actual expiry, so a request doesn't
# lose a race against the token expiring mid-flight.
TOKEN_EXPIRY_BUFFER = timedelta(seconds=60)

class NetSuiteConnectionService:
    """
    Business logic for the NetSuite OAuth connect/callback flow.

    Data-fetching methods (SuiteQL, REST Records) are intentionally not
    implemented yet — this service currently only completes and persists
    the OAuth handshake.
    """

    def __init__(
        self,
        repository: NetSuiteConnectionRepository | None = None,
        client: NetSuiteAuthClient | None = None,
    ):
        self.repository = repository or NetSuiteConnectionRepository()

    def get_authorization_url(self, *, user: User, connection) -> str:
        """Step 1: build the URL the frontend should redirect the browser to."""
        return build_authorization_url(user_id=str(user.id),connection_id=str(connection.id),account_id=connection.netsuite_account_id,
        client_id=connection.client_id,)

    def handle_callback(self, *, code: str, state: str) -> User:
        """
        Step 2: verify `state`, exchange `code` for tokens, and persist
        the connection. Returns the User the connection belongs to (the
        view uses this to decide where to redirect the browser next).
        """
        user_id, connection_id = resolve_user_id_from_state(state)

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist as exc:
            # Only reachable if the user was deleted between /connect/ and
            # NetSuite's redirect back — the signature itself already
            # proved the state wasn't tampered with.
            raise NetSuiteStateMismatchException('Invalid OAuth state parameter.') from exc

        connection = self.repository.get_by_id(
            user=user,
            connection_id=connection_id,
        )
        if connection is None:
            raise NetSuiteConnectionNotFoundException("connection not found.")

        # client = self._get_client()
        client = NetSuiteAuthClient(
        account_id=connection.netsuite_account_id,
        client_id=connection.client_id,
        client_secret=connection.client_secret,
    )
        token_set = client.exchange_code_for_tokens(code=code)

        self.repository.complete_OAuth(
            connection,
            access_token=token_set.access_token,
            refresh_token=token_set.refresh_token,
            access_token_expires_at=token_set.access_token_expires_at,
        )

        logger.info('NetSuite connected for user %s.', user.id)
        return user

    # def _get_client(self) -> NetSuiteAuthClient:
    #     if self._client is None:
    #         self._client = NetSuiteAuthClient()
    #     return self._client

    def list_connections(self,*,user:User):
        return self.repository.list_by_user(user)
    
    def create_connection(
            self,*,
            user:User,
            client_name:str,
            environment:str,
            client_id:str,
            client_secret:str,
            netsuite_account_id:str):
        
        connection = self.repository.create(
            user=user,
            client_name=client_name,
            client_id=client_id,
            environment=environment,
            client_secret=client_secret,
            netsuite_account_id=netsuite_account_id,
        )

        authorization_url = self.get_authorization_url(user=user,connection=connection)

        # return self.repository.create(
        #     user=user,
        #     client_name=client_name,
        #     client_id=client_id,
        #     client_secret=client_secret,
        #     environment=environment,
        #     netsuite_account_id=netsuite_account_id,
        # )
        return {
            "connection":connection,
            "authorization_url":authorization_url,
        }
    
    def rename_connection(
            self,*,
            user:User,
            connection_id,
            client_name:str,
            ):
        connection = self.repository.get_by_id(user,connection_id)

        if connection is None:
            raise NetSuiteConnectionNotFoundException("connection not found.")
        
        return self.repository.rename(
            connection,client_name
        )
    
    def delete_connection(
            self,*,
            user:User,
            connection_id,
    ):
        connection = self.repository.get_by_id(user,connection_id)

        if connection is None:
            raise NetSuiteConnectionNotFoundException("connection not found.")
        
        self.repository.delete(connection)
        # return "connection removed succefully."
    
    def switch_connection(
            self,*,
            user:User,
            connection_id,
    ):
        connection = self.repository.get_by_id(user,connection_id)

        if connection is None:
            raise NetSuiteConnectionNotFoundException("connection not found.")
        
        return self.repository.switch_active_connection(user,connection,)
    

class NetSuiteDataService:
    """
    Fetches live NetSuite record data for an already-connected user.

    Owns the one piece of business logic a plain pass-through read still
    needs: making sure the access token is valid — refreshing it first
    via the existing NetSuiteAuthClient.refresh_access_token() /
    NetSuiteConnectionRepository.update_tokens() if it's expired or about
    to be — before handing off to the Client. No NetSuite response
    shaping happens here; the raw record data is returned as-is.
    """

    def __init__(
        self,
        repository: NetSuiteConnectionRepository | None = None,
    ):
        self.repository = repository or NetSuiteConnectionRepository()

    def _get_authenticated_client(self, user: User) -> NetSuiteAuthClient:
        connection = self._require_connection(user)
        access_token = self._ensure_valid_token(connection)
        
        # client = self._get_client()
        # client.access_token = access_token
        # return client
        client = NetSuiteAuthClient(
        account_id=connection.netsuite_account_id,
        client_id=connection.client_id,
        client_secret=connection.client_secret,
        access_token=access_token,
        )

        return client, connection

    def get_records(
        self,
        *,
        record_type: str,
        user: User,
        limit: int | None = None,
        offset: int | None = None,
        params: dict | None = None,
    ) -> dict:
        client, connection = self._get_authenticated_client(user)
        return self._call_and_track_health(
            connection,
            client.get_records,
            record_type=record_type,
            limit=limit,
            offset=offset,
            params=params,
        )

    def get_record(
        self,
        *,
        record_type: str,
        record_id: str,
        user: User,
        params: dict | None = None,
    ) -> dict:
        client, connection = self._get_authenticated_client(user)
        return self._call_and_track_health(
            connection,
            client.get_record,
            record_type=record_type,
            record_id=record_id,
            params=params,
        )

    def execute_suiteql(self, *, query: str, user: User) -> dict:
        """
        Run a SuiteQL query for `user`'s connected NetSuite account.

        Reuses _get_authenticated_client() — the same connection lookup
        and token-refresh path get_records()/get_record() already use —
        so authentication logic isn't duplicated for SuiteQL. The Client
        (netsuite.client.NetSuiteAuthClient.execute_suiteql) is the only
        thing that actually talks to NetSuite.
        """
        client, connection = self._get_authenticated_client(user)
        return self._call_and_track_health(connection, client.execute_suiteql, query=query)

    def _call_and_track_health(self, connection, client_method, **kwargs) -> dict:
        """
        Runs a NetSuite client call and records the outcome on the
        connection — last_synced_at/last_error/consecutive_failures —
        so connection health is visible without a separate sync/health
        job. Re-raises whatever the client raises; this only observes.
        """
        try:
            result = client_method(**kwargs)
        except Exception as exc:
            self.repository.record_sync_failure(connection, error_message=str(exc))
            raise
        self.repository.record_sync_success(connection)
        return result

    def get_customers(self, *, user: User) -> dict:
        return self.get_records(record_type=NetSuiteRecordType.CUSTOMER, user=user)

    def get_employees(self, *, user: User) -> dict:
        return self.get_records(record_type=NetSuiteRecordType.EMPLOYEE, user=user)

    def get_vendors(self, *, user: User) -> dict:
        return self.get_records(record_type=NetSuiteRecordType.VENDOR, user=user)
    
    def get_sales_orders(self, *, user: User) -> dict:
        return self.get_records(record_type=NetSuiteRecordType.SALES_ORDER, user=user)
    
    def get_purchase_orders(self,*,user: User) -> dict:
        return self.get_records(record_type=NetSuiteRecordType.PURCHASE_ORDER,user=user)
    
    def get_invoices(self,*,user: User) -> dict:
        return self.get_records(record_type=NetSuiteRecordType.INVOICE,user=user)

    def get_items(self, *, user: User, item_type: str = NetSuiteRecordType.INVENTORY_ITEM) -> dict:
        if not NetSuiteRecordType.is_valid(item_type):
            raise ValueError(f"Invalid NetSuite item type: {item_type}")
        return self.get_records(record_type=item_type, user=user)

    def _require_connection(self, user: User):
        connection = self.repository.get_by_user(user)
        if connection is None or not connection.is_active:
            raise NetSuiteConnectionNotFoundException(
                'No active NetSuite connection found. Please connect your NetSuite account first.'
            )
        return connection

    def _ensure_valid_token(self, connection) -> str:
        if timezone.now() < connection.access_token_expires_at - TOKEN_EXPIRY_BUFFER:
            return connection.access_token

        logger.info('Refreshing expired NetSuite access token for user %s.', connection.user_id)
        client = NetSuiteAuthClient(
        account_id=connection.netsuite_account_id,
        client_id=connection.client_id,
        client_secret=connection.client_secret,
        )

        try:
            token_set = client.refresh_access_token(
            refresh_token=connection.refresh_token,
            )
        except Exception as exc:
            self.repository.record_sync_failure(connection, error_message=f'Token refresh failed: {exc}')
            raise

        connection = self.repository.update_tokens(
            connection,
            access_token=token_set.access_token,
            refresh_token=token_set.refresh_token,
            access_token_expires_at=token_set.access_token_expires_at,
        )
        return connection.access_token
