"""
NetSuite OAuth access-token lifecycle management.

Responsibilities
----------------
- Return a currently valid access token.
- Refresh an expired/near-expiry access token exactly once per connection
  at a time by using the database row lock provided by the repository.
- Persist the complete rotated token pair after a successful refresh.
- Treat permanent OAuth failures such as ``invalid_grant`` as a connection
  re-authorization requirement instead of repeatedly retrying a dead token.
- Retry development-time SQLite write contention without ever returning a
  freshly-issued access token while its rotated refresh token was not safely
  persisted.

The actual HTTP/OAuth exchange remains in NetSuiteAuthClient. Database writes
remain in NetSuiteConnectionRepository.
"""

import logging
import time
from datetime import timedelta

from django.db import OperationalError, transaction
from django.utils import timezone

from netsuite.client import NetSuiteAuthClient
from netsuite.exceptions import NetSuiteTokenExchangeException
from netsuite.repositories import NetSuiteConnectionRepository

logger = logging.getLogger(__name__)


# Refresh proactively slightly before actual expiry so a token does not expire
# in the middle of a live NetSuite request.
TOKEN_EXPIRY_BUFFER = timedelta(seconds=60)

# SQLite is used only for local development. PostgreSQL is expected in
# production, where the repository's SELECT ... FOR UPDATE provides the
# concurrency guarantee for refresh-token rotation.
SQLITE_PERSIST_RETRIES = 3
SQLITE_RETRY_BASE_DELAY_SECONDS = 0.5


class NetSuiteTokenManager:
    def __init__(
        self,
        repository: NetSuiteConnectionRepository | None = None,
    ):
        self.repository = repository or NetSuiteConnectionRepository()

    @staticmethod
    def _token_is_usable(connection, *, now=None) -> bool:
        """Return True only when a non-empty access token is safely usable."""
        now = now or timezone.now()

        return bool(
            connection.access_token
            and connection.access_token_expires_at
            and now < (
                connection.access_token_expires_at - TOKEN_EXPIRY_BUFFER
            )
        )

    @staticmethod
    def _invalid_grant_message() -> str:
        return (
            "NetSuite refresh token is no longer valid. "
            "Re-authorization is required."
        )

    def get_valid_access_token(self, connection) -> str:
        """
        Return a valid access token for ``connection``.

        Fast path:
            Return the existing token when it is still valid.

        Refresh path:
            Acquire the repository's row lock, re-check the token because
            another request may have refreshed it while this request waited,
            then perform exactly one refresh if it is still required.

        A refreshed token is never returned until the complete rotated token
        pair has been persisted successfully.
        """
        if connection is None:
            raise ValueError("NetSuite connection is required.")

        if self._token_is_usable(connection):
            return connection.access_token

        invalid_grant_error = None
        access_token = None

        try:
            with transaction.atomic():
                locked_connection = self.repository.get_locked(connection.id)
    
                if self._token_is_usable(locked_connection):
                    return locked_connection.access_token

                return self._refresh(locked_connection)

        except NetSuiteTokenExchangeException  as exc:
            if str(exc).startswith("NETSUITE_INVALID_GRANT:"):
                invalid_grant_error  = exc
            else:
                raise

        if invalid_grant_error is not None:
            self.repository.mark_token_invalid(
                connection,
                error_message=self._invalid_grant_message(),
            )
            raise invalid_grant_error

    
        # return self._refresh(locked_connection)
        return access_token

    def _refresh(self, connection) -> str:
        """
        Refresh a connection's OAuth credentials and persist the new token set.

        NetSuite rotates refresh tokens. Therefore a successful refresh is an
        atomic business operation from our application's perspective:

            refresh at NetSuite -> persist BOTH access + refresh token -> return

        If persistence fails, the new access token is deliberately NOT returned
        because doing so could leave the database holding a superseded refresh
        token and cause the next refresh to fail with ``invalid_grant``.
        """

        if not connection.refresh_token:
            # A connection with no refresh token cannot recover silently.
            # This can happen after a permanent OAuth failure has been marked.
            raise NetSuiteTokenExchangeException(
                "NETSUITE_INVALID_GRANT: " + self._invalid_grant_message()
            )

        logger.info(
            "Refreshing expired NetSuite access token for user %s.",
            connection.user_id,
        )

        client = NetSuiteAuthClient(
            account_id=connection.netsuite_account_id,
            client_id=connection.client_id,
            client_secret=connection.client_secret,
        )

        try:
            # Never retry this HTTP call. NetSuite can rotate the refresh token
            # on use, so retrying can send a token that was already superseded.
            token_set = client.refresh_access_token(
                refresh_token=connection.refresh_token,
            )
        except NetSuiteTokenExchangeException as exc:
            message = str(exc)

            if message.startswith("NETSUITE_INVALID_GRANT:"):
                raise

            self.repository.record_sync_failure(
                connection,
                error_message=f"Token refresh failed: {message}",
            )
            raise
        except Exception as exc:
            self.repository.record_sync_failure(
                connection,
                error_message=f"Token refresh failed: {exc}",
            )
            raise

        # Defensive validation: a successful OAuth response must contain both
        # values required for the next refresh cycle.
        if not token_set.access_token:
            raise NetSuiteTokenExchangeException(
                "NetSuite token endpoint returned no access token."
            )

        if not token_set.refresh_token:
            raise NetSuiteTokenExchangeException(
                "NetSuite token endpoint returned no refresh token."
            )

        updated_connection = None

        for attempt in range(1, SQLITE_PERSIST_RETRIES + 1):
            try:
                updated_connection = self.repository.update_tokens(
                    connection,
                    access_token=token_set.access_token,
                    refresh_token=token_set.refresh_token,
                    access_token_expires_at=token_set.access_token_expires_at,
                    # NetSuiteTokenSet currently does not expose a refresh-token
                    # expiry timestamp. Preserve the existing value until the
                    # client model explicitly supports one.
                    refresh_token_expires_at=connection.refresh_token_expires_at,
                )
                break

            except OperationalError as exc:
                if "database is locked" not in str(exc).lower():
                    raise

                if attempt >= SQLITE_PERSIST_RETRIES:
                    logger.error(
                        "Unable to persist refreshed NetSuite token after %s "
                        "SQLite retry attempts — connection=%s",
                        attempt,
                        connection.id,
                    )
                    raise

                delay = (
                    SQLITE_RETRY_BASE_DELAY_SECONDS * attempt
                )

                logger.warning(
                    "SQLite locked while persisting refreshed NetSuite token; "
                    "retrying in %.1fs — attempt=%s/%s connection=%s",
                    delay,
                    attempt,
                    SQLITE_PERSIST_RETRIES,
                    connection.id,
                )

                time.sleep(delay)

        if updated_connection is None:
            # Defensive guard; normally unreachable because the final failed
            # attempt raises above.
            raise RuntimeError(
                "Unable to persist refreshed NetSuite credentials."
            )

        return updated_connection.access_token
