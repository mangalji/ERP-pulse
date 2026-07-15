"""
NetSuite Client — the only place in this module that speaks HTTP to
NetSuite.

Per NETSUITE_CONTEXT.md ("Client Layer... should never contain business
logic" / "No module may call requests.get() directly"), this class is
authentication/HTTP only: build the request, send it, translate the
response or a transport failure into typed data or an exception.
Persisting or interpreting tokens/records is the Service layer's job
(services.py).

Handles both halves of NetSuite communication: the OAuth 2.0 token
endpoint (exchange/refresh) and, as of this task, authenticated REST
Record reads. Kept as one class per NETSUITE_CONTEXT.md's "Only the
NetSuiteClient" rule, and to avoid an unnecessary second class for what
is still a handful of methods; the name predates record support but
renaming now would touch every existing import for no functional gain.

SuiteQL is intentionally not implemented — plain REST Record endpoints
are enough for this step.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

import requests
from django.conf import settings
from django.utils import timezone

from netsuite.constants import NetSuiteRecordType
from netsuite.exceptions import (
    NetSuiteConfigurationException, 
    NetSuiteTokenExchangeException, 
    NetSuiteRecordFetchException,
    NetSuiteRecordNotFoundException,
    )
from netsuite.oauth import netsuite_account_domain

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT_SECONDS = 15


@dataclass(frozen=True)
class NetSuiteTokenSet:
    """Normalized result of a token exchange or refresh call."""

    access_token: str
    refresh_token: str
    access_token_expires_at: datetime


class NetSuiteAuthClient:
    """Handles the token-endpoint calls of the OAuth 2.0 Authorization Code Grant."""

    def __init__(self, access_token: str | None = None):
        self.account_id = settings.NETSUITE_ACCOUNT_ID
        self.client_id = settings.NETSUITE_CLIENT_ID
        self.client_secret = settings.NETSUITE_CLIENT_SECRET
        self.redirect_uri = settings.NETSUITE_REDIRECT_URI
        self.access_token = access_token

        if not all([self.account_id, self.client_id, self.client_secret, self.redirect_uri]):
            raise NetSuiteConfigurationException(
                'NetSuite OAuth is not configured. Set NETSUITE_ACCOUNT_ID, '
                'NETSUITE_CLIENT_ID, NETSUITE_CLIENT_SECRET, and NETSUITE_REDIRECT_URI.'
            )

        domain = netsuite_account_domain(self.account_id)
        self._rest_base_url = f'https://{domain}.suitetalk.api.netsuite.com/services/rest'
        self._token_url = f'{self._rest_base_url}/auth/oauth2/v1/token'

    def exchange_code_for_tokens(self, *, code: str) -> NetSuiteTokenSet:
        """Step 2 of the Authorization Code Grant: trade an auth code for tokens."""
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

    def get_customers(self, *, access_token: str | None = None) -> dict:
        """
        GET /record/v1/customer — NetSuite's REST Record collection endpoint.
        Kept for 100% backward compatibility.
        """
        return self.get_records(
            record_type=NetSuiteRecordType.CUSTOMER,
            access_token=access_token,
        )

    def _get(self, *, path: str, access_token: str | None = None, params: dict | None = None) -> dict:
        token = access_token or self.access_token
        if not token:
            raise ValueError("No access token provided or stored on client.")

        try:
            response = requests.get(
                f'{self._rest_base_url}/{path}',
                headers={
                    'Authorization': f'Bearer {token}',
                    'Content-Type': 'application/json',
                },
                params=params,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
        except requests.RequestException as exc:
            logger.exception('NetSuite record request failed (network error).')
            raise NetSuiteRecordFetchException(
                'Could not reach NetSuite to fetch records. Please try again.'
            ) from exc
        
        if response.status_code == 404:
            logger.error('NetSuite record endpoint returned 404 for %s.',path)
            raise NetSuiteRecordNotFoundException('The requested NetSuite record was not found.')

        if not response.ok:
            logger.error('NetSuite record endpoint returned %s for %s.', response.status_code, path)
            raise NetSuiteRecordFetchException(
                'NetSuite rejected the record request. Please reconnect your account.'
            )

        return response.json()

    def _post_token_request(self, data: dict) -> NetSuiteTokenSet:
        try:
            response = requests.post(
                self._token_url,
                data=data,
                auth=(self.client_id, self.client_secret),
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
        except requests.RequestException as exc:
            logger.exception('NetSuite token request failed (network error).')
            raise NetSuiteTokenExchangeException(
                'Could not reach NetSuite to complete authentication. Please try again.'
            ) from exc

        if not response.ok:
            # Never log the request body (contains the auth code/refresh
            # token) or raw response body — NETSUITE_CONTEXT.md
            # "Never log credentials."
            logger.error('NetSuite token endpoint returned %s.', response.status_code)
            raise NetSuiteTokenExchangeException(
                'NetSuite rejected the authentication request. Please reconnect your account.'
            )
        payload = response.json()
        expires_in = payload.get('expires_in', 3600)

        return NetSuiteTokenSet(
            access_token=payload['access_token'],
            # refresh_token=payload['refresh_token'],
            refresh_token=payload.get('refresh_token',data.get('refresh_token')),
            access_token_expires_at=timezone.now() + timedelta(seconds=expires_in),
        )
