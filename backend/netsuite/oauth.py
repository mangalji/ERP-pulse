"""
NetSuite OAuth 2.0 Authorization Code Grant — URL building and state
signing.

This module owns the "browser redirect" half of the flow (building the
authorize URL, protecting it with a signed `state`). The
"server-to-server" half — exchanging the code for tokens — lives in
client.py, since that's an HTTP call, not URL/protocol construction.

Reference: NetSuite OAuth 2.0 Authorization Code Grant Flow
(docs.oracle.com, section_158074210415 / section_160855585734).
"""

from urllib.parse import urlencode

from django.conf import settings
from django.core import signing

from netsuite.exceptions import NetSuiteConfigurationException, NetSuiteStateMismatchException

# Read-only scope only: this MVP never writes to NetSuite
# (NETSUITE_CONTEXT.md — "ERP Pulse is primarily a Read-Only Integration").
OAUTH_SCOPE = 'rest_webservices'

# How long a signed `state` value remains valid — generous enough to
# cover a user sitting on NetSuite's login/consent screen, short enough
# that a leaked callback URL can't be replayed indefinitely.
STATE_MAX_AGE_SECONDS = 600

_state_signer = signing.TimestampSigner(salt='netsuite-oauth-state')


def netsuite_account_domain(account_id: str) -> str:
    """
    NetSuite account-specific subdomains use hyphens, not underscores —
    e.g. sandbox account `1234567_SB1` becomes `1234567-sb1` in the host.
    Shared by oauth.py (authorize URL) and client.py (token endpoint URL).
    """
    return account_id.lower().replace('_', '-')


def build_authorization_url(*, user_id: str) -> str:
    """
    Build the NetSuite OAuth 2.0 authorize URL for a given ERP Pulse user.

    `state` is a signed, timestamped token encoding `user_id` — not a
    random opaque value stored in a database table. This lets
    resolve_user_id_from_state() recover *which* user is completing the
    flow without a server-side session (the callback is a plain browser
    GET from NetSuite, so it carries no JWT), while still
    cryptographically guaranteeing the value wasn't tampered with or
    replayed after STATE_MAX_AGE_SECONDS.
    """
    account_id = settings.NETSUITE_ACCOUNT_ID
    client_id = settings.NETSUITE_CLIENT_ID
    redirect_uri = settings.NETSUITE_REDIRECT_URI

    if not all([account_id, client_id, redirect_uri]):
        raise NetSuiteConfigurationException(
            'NetSuite OAuth is not configured. Set NETSUITE_ACCOUNT_ID, '
            'NETSUITE_CLIENT_ID, and NETSUITE_REDIRECT_URI.'
        )

    state = _state_signer.sign(str(user_id))

    query = urlencode({
        'response_type': 'code',
        'client_id': client_id,
        'redirect_uri': redirect_uri,
        'scope': OAUTH_SCOPE,
        'state': state,
    })

    domain = netsuite_account_domain(account_id)
    return f'https://{domain}.app.netsuite.com/app/login/oauth2/authorize.nl?{query}'


def resolve_user_id_from_state(state: str) -> str:
    """
    Verify a `state` value's signature and age, and return the user_id it
    encodes. Raises NetSuiteStateMismatchException if the value is
    missing, malformed, expired, or tampered with.
    """
    if not state:
        raise NetSuiteStateMismatchException('Missing OAuth state parameter.')

    try:
        return _state_signer.unsign(state, max_age=STATE_MAX_AGE_SECONDS)
    except signing.SignatureExpired as exc:
        raise NetSuiteStateMismatchException(
            'OAuth state has expired. Please try connecting again.'
        ) from exc
    except signing.BadSignature as exc:
        raise NetSuiteStateMismatchException('Invalid OAuth state parameter.') from exc
