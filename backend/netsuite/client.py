"""
NetSuite Auth Client — the only place in this module that speaks HTTP to
NetSuite's OAuth 2.0 token endpoint.

Per NETSUITE_CONTEXT.md ("Client Layer... should never contain business
logic" / "No module may call requests.get() directly"), this class is
authentication/HTTP only: build the request, send it, translate the
response or a transport failure into typed data or a
NetSuiteTokenExchangeException. Persisting or interpreting tokens is
NetSuiteConnectionService's job (services.py).

Data-fetching methods (SuiteQL, REST Record API) are intentionally not
implemented yet — this class currently only completes the OAuth handshake.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

import requests
from django.conf import settings
from django.utils import timezone

from netsuite.exceptions import NetSuiteConfigurationException, NetSuiteTokenExchangeException
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

    def __init__(self):
        self.account_id = settings.NETSUITE_ACCOUNT_ID
        self.client_id = settings.NETSUITE_CLIENT_ID
        self.client_secret = settings.NETSUITE_CLIENT_SECRET
        self.redirect_uri = settings.NETSUITE_REDIRECT_URI

        if not all([self.account_id, self.client_id, self.client_secret, self.redirect_uri]):
            raise NetSuiteConfigurationException(
                'NetSuite OAuth is not configured. Set NETSUITE_ACCOUNT_ID, '
                'NETSUITE_CLIENT_ID, NETSUITE_CLIENT_SECRET, and NETSUITE_REDIRECT_URI.'
            )

        domain = netsuite_account_domain(self.account_id)
        self._token_url = (
            f'https://{domain}.suitetalk.api.netsuite.com/services/rest/auth/oauth2/v1/token'
        )

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
            refresh_token=payload['refresh_token'],
            access_token_expires_at=timezone.now() + timedelta(seconds=expires_in),
        )
