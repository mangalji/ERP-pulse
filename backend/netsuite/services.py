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
from netsuite.exceptions import NetSuiteStateMismatchException
from netsuite.oauth import build_authorization_url, resolve_user_id_from_state
from netsuite.repositories import NetSuiteConnectionRepository

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
    ):
        self.repository = repository or NetSuiteConnectionRepository()
        self._client = client

    def get_authorization_url(self, *, user: User) -> str:
        """Step 1: build the URL the frontend should redirect the browser to."""
        return build_authorization_url(user_id=str(user.id))

    def handle_callback(self, *, code: str, state: str) -> User:
        """
        Step 2: verify `state`, exchange `code` for tokens, and persist
        the connection. Returns the User the connection belongs to (the
        view uses this to decide where to redirect the browser next).
        """
        user_id = resolve_user_id_from_state(state)

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist as exc:
            # Only reachable if the user was deleted between /connect/ and
            # NetSuite's redirect back — the signature itself already
            # proved the state wasn't tampered with.
            raise NetSuiteStateMismatchException('Invalid OAuth state parameter.') from exc

        client = self._get_client()
        token_set = client.exchange_code_for_tokens(code=code)

        self.repository.upsert(
            user=user,
            netsuite_account_id=client.account_id,
            access_token=token_set.access_token,
            refresh_token=token_set.refresh_token,
            access_token_expires_at=token_set.access_token_expires_at,
        )

        logger.info('NetSuite connected for user %s.', user.id)
        return user

    def _get_client(self) -> NetSuiteAuthClient:
        if self._client is None:
            self._client = NetSuiteAuthClient()
        return self._client
