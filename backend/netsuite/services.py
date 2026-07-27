"""
Business logic for connecting an ERP Pulse user's NetSuite account.

Orchestrates oauth.py (URL/state), NetSuiteAuthClient (token exchange),
and NetSuiteConnectionRepository (persistence) — the view layer never
touches any of those directly, mirroring how AuthenticationService
orchestrates UserRepository/OTPService for the accounts app.
"""

import logging
from accounts.models import User
from netsuite.client import NetSuiteAuthClient
from netsuite.constants import NetSuiteRecordType
from netsuite.exceptions import NetSuiteStateMismatchException, NetSuiteConnectionNotFoundException, NetSuiteConnectionAlreadyExistsException
from netsuite.oauth import build_authorization_url, resolve_user_id_from_state
from netsuite.repositories import NetSuiteConnectionAuditLogRepository, NetSuiteConnectionRepository
from netsuite.token_manager import NetSuiteTokenManager

logger = logging.getLogger(__name__)

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
        audit_log_repository: NetSuiteConnectionAuditLogRepository | None = None,
    ):
        self.repository = repository or NetSuiteConnectionRepository()
        self.audit_log_repository = audit_log_repository or NetSuiteConnectionAuditLogRepository()

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
        self.audit_log_repository.log(action='oauth_completed', connection=connection)

        logger.info('NetSuite connected for user %s.', user.id)
        return user

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

        if self.repository.exists_for_account(user,netsuite_account_id):
            raise NetSuiteConnectionAlreadyExistsException(
                "You alreadty have a connection for this netsuite account"
            )
        
        connection = self.repository.create(
            user=user,
            client_name=client_name,
            client_id=client_id,
            environment=environment,
            client_secret=client_secret,
            netsuite_account_id=netsuite_account_id,
        )
        self.audit_log_repository.log(action='created', connection=connection)

        authorization_url = self.get_authorization_url(user=user,connection=connection)

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

        old_name = connection.client_name
        renamed = self.repository.rename(
            connection,client_name
        )
        self.audit_log_repository.log(
            action='renamed', connection=renamed,
            detail=f'"{old_name}" -> "{client_name}"',
        )
        return renamed
    
    def delete_connection(
            self,*,
            user:User,
            connection_id,
    ):
        connection = self.repository.get_by_id(user,connection_id)

        if connection is None:
            raise NetSuiteConnectionNotFoundException("connection not found.")

        self.audit_log_repository.log(action='deleted', connection=connection)
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

        switched = self.repository.switch_active_connection(user,connection,)
        self.audit_log_repository.log(action='switched_active', connection=switched)
        return switched
    

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
        token_manager: NetSuiteTokenManager | None = None,
    ):
        self.repository = repository or NetSuiteConnectionRepository()
        self.token_manager = token_manager or NetSuiteTokenManager(repository=self.repository)

    def _get_authenticated_client(self, user: User) -> NetSuiteAuthClient:
        connection = self._require_connection(user)
        access_token = self.token_manager.get_valid_access_token(connection)

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
        self.repository.touch_last_used(connection)
        return result

    def get_customers(self, *, user: User, limit: int | None = None, offset: int | None = None) -> dict:
        return self.get_records(record_type=NetSuiteRecordType.CUSTOMER, user=user, limit=limit, offset=offset)

    def get_employees(self, *, user: User, limit: int | None = None, offset: int | None = None) -> dict:
        return self.get_records(record_type=NetSuiteRecordType.EMPLOYEE, user=user, limit=limit, offset=offset)

    def get_vendors(self, *, user: User, limit: int | None = None, offset: int | None = None) -> dict:
        return self.get_records(record_type=NetSuiteRecordType.VENDOR, user=user, limit=limit, offset=offset)

    def get_sales_orders(self, *, user: User, limit: int | None = None, offset: int | None = None) -> dict:
        return self.get_records(record_type=NetSuiteRecordType.SALES_ORDER, user=user, limit=limit, offset=offset)
    
    def get_purchase_orders(self, *, user: User, limit: int | None = None, offset: int | None = None) -> dict:
        return self.get_records(record_type=NetSuiteRecordType.PURCHASE_ORDER, user=user, limit=limit, offset=offset)
    
    def get_invoices(self, *, user: User, limit: int | None = None, offset: int | None = None) -> dict:
        return self.get_records(record_type=NetSuiteRecordType.INVOICE, user=user, limit=limit, offset=offset)

    def get_items(self, *, user: User, item_type: str = NetSuiteRecordType.INVENTORY_ITEM, limit: int | None = None, offset: int | None = None) -> dict:
        if not NetSuiteRecordType.is_valid(item_type):
            raise ValueError(f"Invalid NetSuite item type: {item_type}")
        return self.get_records(record_type=item_type, user=user, limit=limit, offset=offset)

    def _require_connection(self, user: User):
        connection = self.repository.get_by_user(user)
        if connection is None or not connection.is_active:
            raise NetSuiteConnectionNotFoundException(
                'No active NetSuite connection found. Please connect your NetSuite account first.'
            )
        return connection