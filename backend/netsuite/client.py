"""
NetSuite Client — the only place in this module that speaks HTTP to
NetSuite.

Per NETSUITE_CONTEXT.md ("Client Layer... should never contain business
logic" / "No module may call requests.get() directly"), this class is
authentication/HTTP only: build the request, send it via netsuite/http.py,
translate the response (via netsuite/errors.py) or a transport failure
into typed data or an exception. Persisting or interpreting tokens/records
is the Service layer's job (services.py).

Handles both halves of NetSuite communication: the OAuth 2.0 token
endpoint (exchange/refresh) and authenticated REST Record reads plus
SuiteQL. Kept as one class per NETSUITE_CONTEXT.md's "Only the
NetSuiteClient" rule, and to avoid an unnecessary second class for what
is still a handful of methods; the name predates record/SuiteQL support
but renaming now would touch every existing import for no functional
gain.

HTTP sending (timeout, correlation ID, retry/backoff) lives in
netsuite/http.py. Response-to-exception mapping lives in
netsuite/errors.py. This split (P1) keeps this file focused on "what
NetSuite endpoints exist and how to call them" — public method
signatures are unchanged from before the split.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

from django.conf import settings
from django.utils import timezone

from netsuite import errors, http
from netsuite.constants import NetSuiteRecordType
from netsuite.exceptions import (
    NetSuiteConfigurationException,
    NetSuiteRecordFetchException,
    NetSuiteTokenExchangeException,
)
from netsuite.oauth import netsuite_account_domain

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class NetSuiteTokenSet:
    """Normalized result of a token exchange or refresh call."""

    access_token: str
    refresh_token: str
    access_token_expires_at: datetime


class NetSuiteAuthClient:
    """Handles the token-endpoint calls of the OAuth 2.0 Authorization Code Grant."""

    def __init__(self,
                *,
                account_id:str,
                client_id:str,
                client_secret:str,
                access_token: str | None = None):
        self.account_id = account_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = settings.NETSUITE_REDIRECT_URI
        self.access_token = access_token

        if not all([self.account_id, self.client_id, self.client_secret, self.redirect_uri]):
            raise NetSuiteConfigurationException(
                'NetSuite OAuth is not configured.'
            )

        domain = netsuite_account_domain(self.account_id)
        self._rest_base_url = f'https://{domain}.suitetalk.api.netsuite.com/services/rest'
        self._token_url = f'{self._rest_base_url}/auth/oauth2/v1/token'

    def exchange_code_for_tokens(self, *, code: str) -> NetSuiteTokenSet:
        """
        Step 2 of the Authorization Code Grant: trade an auth code for tokens.

        Never retried — an authorization code is single-use, so retrying
        this call after a transient failure would send an
        already-consumed code.
        """
        return self._post_token_request({
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': self.redirect_uri,
        })

    def refresh_access_token(self, *, refresh_token: str) -> NetSuiteTokenSet:
        """
        Exchange a refresh token for a new access token. NetSuite issues a
        new refresh token on every refresh, so the caller must persist
        both returned values, not just the access token.

        Not retried, for the same reason as exchange_code_for_tokens —
        NetSuite may rotate the refresh token on each use, so a retried
        call could present an already-superseded token.
        """
        return self._post_token_request({
            'grant_type': 'refresh_token',
            'refresh_token': refresh_token,
        })

    def get_records(
        self,
        *,
        record_type: str,
        limit: int | None = None,
        offset: int | None = None,
        params: dict | None = None,
        access_token: str | None = None,
    ) -> dict:
        """
        GET /record/v1/{record_type} — generic NetSuite REST Record
        collection endpoint.
        """
        if not NetSuiteRecordType.is_valid(record_type):
            raise ValueError(f"Unsupported record type: {record_type}")

        query_params = params.copy() if params else {}
        if limit is not None:
            query_params['limit'] = limit
        if offset is not None:
            query_params['offset'] = offset

        return self._get(
            path=f'record/v1/{record_type}',
            access_token=access_token,
            params=query_params,
        )

    def get_record(
        self,
        *,
        record_type: str,
        record_id: str,
        params: dict | None = None,
        access_token: str | None = None,
    ) -> dict:
        """
        GET /record/v1/{record_type}/{id} — generic NetSuite REST Record
        single-item endpoint.
        """
        if not NetSuiteRecordType.is_valid(record_type):
            raise ValueError(f"Unsupported record type: {record_type}")

        return self._get(
            path=f'record/v1/{record_type}/{record_id}',
            access_token=access_token,
            params=params,
        )

    def create_record(
        self,
        *,
        record_type: str,
        data: dict,
        access_token: str | None = None,
        ) -> dict:
        """Create a NetSuite REST record without retrying the mutation."""
        if not record_type:
            raise ValueError("Unsupported NetSuite record type.")
        if not isinstance(data, dict):
            raise ValueError("NetSuite record payload must be a JSON object.")

        return self._post(
            path=f"record/v1/{record_type}",
            access_token=access_token,
            data=data,
            retryable=False,
        )

    def get_customers(self, *, access_token: str | None = None) -> dict:
        """
        GET /record/v1/customer — NetSuite's REST Record collection endpoint.
        Kept for 100% backward compatibility.
        """
        return self.get_records(
            record_type=NetSuiteRecordType.CUSTOMER,
            access_token=access_token,
        )

    def execute_suiteql(
        self,
        *,
        query: str,
        limit: int | None = None,
        offset: int | None = None,
        access_token: str | None = None,
    ) -> dict:
        """
        Execute a SuiteQL query.

        Intended for analytics and reporting where REST Record endpoints
        are insufficient because of pagination limitations.

        limit/offset are NOT embedded in the SQL text — NetSuite's
        documented SuiteQL pagination mechanism is URL query params on
        the POST itself (POST /query/v1/suiteql?limit=X&offset=Y),
        exactly like the REST Record collection endpoint. Response shape
        then includes `count`, `offset`, `totalResults`, and `hasMore`
        alongside `items`, same envelope as get_records().
        """
        query_params = {}
        if limit is not None:
            query_params['limit'] = limit
        if offset is not None:
            query_params['offset'] = offset

        return self._post(
            path="query/v1/suiteql",
            access_token=access_token,
            params=query_params or None,
            data={
                "q": query,
            },
            headers={
                "Prefer": "transient",
            },
            retryable=True,
        )

    # -----------------------------------------------------------------
    # Internal request helpers
    # -----------------------------------------------------------------

    def _get(self, *, path: str, access_token: str | None = None, params: dict | None = None) -> dict:
        token = access_token or self.access_token
        if not token:
            raise ValueError("No access token provided or stored on client.")

        correlation_id = http.new_correlation_id()
        try:
            response = http.send(
                'GET',
                f'{self._rest_base_url}/{path}',
                headers={
                    'Authorization': f'Bearer {token}',
                    'Content-Type': 'application/json',
                },
                params=params,
                retryable=True,  # GET is idempotent — safe to retry on 429/5xx
                correlation_id=correlation_id,
            )
        except Exception as exc:
            logger.exception(
                'NetSuite record request failed (network error). correlation_id=%s', correlation_id,
            )
            raise NetSuiteRecordFetchException(
                'Could not reach NetSuite to fetch records. Please try again.'
            ) from exc

        errors.raise_for_record_response(response, path=path)
        return response.json()

    def _post(
        self,
        *,
        path: str,
        access_token: str | None = None,
        data: dict | None = None,
        headers: dict | None = None,
        params: dict | None = None,
        retryable: bool = True,
    ) -> dict:
        """
        Generic authenticated POST helper.

        Used by SuiteQL (read-only queries) and any future authenticated
        POST endpoints. retryable=True here assumes the call is
        idempotent/read-only, which holds for SuiteQL — if this helper is
        ever used for a mutating POST, that call site should pass its own
        non-retrying path instead of reusing this one as-is.
        """
        token = access_token or self.access_token

        if not token:
            raise ValueError("No access token provided or stored on client.")

        request_headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        if headers:
            request_headers.update(headers)

        correlation_id = http.new_correlation_id()
        try:
            response = http.send(
                'POST',
                f"{self._rest_base_url}/{path}",
                headers=request_headers,
                json=data,
                params=params,
                retryable=retryable,
                correlation_id=correlation_id,
            )
        except Exception as exc:
            logger.exception(
                "NetSuite POST request failed (network error). correlation_id=%s", correlation_id,
            )
            raise NetSuiteRecordFetchException(
                "Could not reach NetSuite to complete the POST request. Please try again."
            ) from exc

        errors.raise_for_record_response(response, path=path)

        try:
            return response.json()
        except ValueError as exc:
            logger.exception("Invalid JSON returned by NetSuite. correlation_id=%s", correlation_id)
            raise NetSuiteRecordFetchException(
                "NetSuite returned an invalid response."
            ) from exc

    def _post_token_request(self, data: dict) -> NetSuiteTokenSet:
        correlation_id = http.new_correlation_id()
        try:
            response = http.send(
                'POST',
                self._token_url,
                data=data,
                auth=(self.client_id, self.client_secret),
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
                retryable=False,  # never retry — see method docstrings above
                correlation_id=correlation_id,
            )
        except Exception as exc:
            logger.exception(
                'NetSuite token request failed (network error). correlation_id=%s', correlation_id,
            )
            raise NetSuiteTokenExchangeException(
                'Could not reach NetSuite to complete authentication. Please try again.'
            ) from exc

        if not response.ok:
            # Never log the request body (contains the auth code/refresh
            # token) or raw response body — NETSUITE_CONTEXT.md
            # "Never log credentials."
            logger.error(
                'NetSuite token endpoint returned %s. correlation_id=%s',
                response.status_code, correlation_id,
            )
        errors.raise_for_token_response(response)

        payload = response.json()
        expires_in = payload.get('expires_in', 3600)

        return NetSuiteTokenSet(
            access_token=payload['access_token'],
            refresh_token=payload.get('refresh_token', data.get('refresh_token')),
            access_token_expires_at=timezone.now() + timedelta(seconds=expires_in),
        )