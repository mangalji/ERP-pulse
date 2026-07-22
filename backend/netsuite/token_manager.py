"""
Owns NetSuite access-token validity/refresh for a connection.

Extracted from NetSuiteDataService._ensure_valid_token() (single
responsibility: "is this connection's token still good, and if not, get
a new one" is a distinct concern from "fetch this record type").

Why the lock exists: without it, two requests arriving while a
connection's token is expired can both decide to refresh at once. NetSuite
rotates refresh tokens on use, so the second concurrent refresh call can
fail (using an already-rotated refresh token), or the two resulting DB
writes can race and leave a stale token pair persisted. Locking with
Postgres' SELECT ... FOR UPDATE (via
NetSuiteConnectionRepository.get_locked) serializes refreshes per
connection: the second request waits for the first to commit, then
re-checks expiry under the lock and finds the token already refreshed —
so at most one real NetSuite refresh call happens per expiry.

No new infrastructure (Redis/Celery locks) — this is DB-native, matching
the existing modular-monolith / no-unnecessary-frameworks approach the
rest of the repository layer already uses for its own multi-row writes
(see switch_active_connection, delete, complete_OAuth).
"""
import logging
from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from netsuite.client import NetSuiteAuthClient
from netsuite.repositories import NetSuiteConnectionRepository

# Refresh proactively slightly before actual expiry, so a request doesn't
# lose a race against the token expiring mid-flight.
TOKEN_EXPIRY_BUFFER = timedelta(seconds=60)

class NetSuiteTokenManager:
    def __init__(self,repository : NetSuiteConnectionRepository | None = None):
        self.repository = repository or NetSuiteConnectionRepository()

    def get_valid_access_token(self,connection) -> str:
        """
        Return a valid access token for `connection`, refreshing it first
        if it's expired or about to expire. Safe to call concurrently for
        the same connection — only one caller will actually hit NetSuite's
        refresh endpoint; the rest will see the already-refreshed token
        once they acquire the row lock.
        """
        if timezone.now() < connection.access_token_expires_at - TOKEN_EXPIRY_BUFFER:
            return connection.access_token
        
        with transaction.atomic():
            locked_connection = self.repository.get_locked(connection.id)

            # Another request may have already refreshed this connection
            # while we were waiting for the lock — re-check before calling
            # NetSuite again.
            
            if timezone.now() < locked_connection.access_token_expires_at - TOKEN_EXPIRY_BUFFER:
                return locked_connection.access_token

            return self._refresh(locked_connection)
        
    def _refresh(self,connection) -> str:
        logger = logging.getLogger(__name__)
        logger.info('Refreshing expired NetSuite access token for user %s.',connection.user_id)

        client = NetSuiteAuthClient(
            account_id=connection.netsuite_account_id,
            client_id=connection.client_id,
            client_secret=connection.client_secret,
        )
        try:
            token_set = client.refresh_access_token(refresh_token=connection.refresh_token)
        except Exception as exc:
            self.repository.record_sync_failure(connection,error_message=f'Token refresh failed: {exc}')
            raise
        updated_connection = self.repository.update_tokens(
            connection,
            access_token=token_set.access_token,
            refresh_token=token_set.refresh_token,
            access_token_expires_at=token_set.access_token_expires_at,
        )
        return updated_connection.access_token