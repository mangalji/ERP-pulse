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

import json
from typing import TypedDict
from urllib.parse import urlencode

from django.conf import settings
from django.core import signing

from netsuite.exceptions import NetSuiteConfigurationException, NetSuiteStateMismatchException

# Read-only scope only: this MVP never writes to NetSuite
OAUTH_SCOPE = 'rest_webservices'

# How long a signed `state` value remains valid — generous enough to
# cover a user sitting on NetSuite's login/consent screen, short enough
# that a leaked callback URL can't be replayed indefinitely.
STATE_MAX_AGE_SECONDS = 600

class OAuthStatePayload(TypedDict):
    user_id: str
    connection_id: str
    post_connect_redirect_url: str | None

_state_signer = signing.TimestampSigner(salt='netsuite-oauth-state')


def netsuite_account_domain(account_id: str) -> str:
    """
    NetSuite account-specific subdomains use hyphens, not underscores —
    e.g. sandbox account `1234567_SB1` becomes `1234567-sb1` in the host.
    Shared by oauth.py (authorize URL) and client.py (token endpoint URL).
    """
    return account_id.lower().replace('_', '-')


def netsuite_vendor_bill_url(*, account_id: str, record_id: str) -> str:
    """Return the browser URL for a Vendor Bill created through SuiteTalk."""
    query = urlencode({"id": str(record_id), "whence": ""})
    return (
        f"https://{netsuite_account_domain(account_id)}.app.netsuite.com"
        f"/app/accounting/transactions/vendbill.nl?{query}"
    )


def build_authorization_url(*, user_id: str, connection_id: str, account_id: str, client_id: str,post_connect_redirect_url: str | None = None) -> str:
    """
    Build the NetSuite OAuth 2.0 authorize URL for a given AGSuite ERP user.

    `state` is a signed, timestamped token encoding `user_id` — not a
    random opaque value stored in a database table. This lets
    resolve_user_id_from_state() recover *which* user is completing the
    flow without a server-side session (the callback is a plain browser
    GET from NetSuite, so it carries no JWT), while still
    cryptographically guaranteeing the value wasn't tampered with or
    replayed after STATE_MAX_AGE_SECONDS.
    """

    redirect_uri = settings.NETSUITE_REDIRECT_URI

    if not redirect_uri:
        raise NetSuiteConfigurationException(
            "NETSUITE_REDIRECT_URI is not configured."
        )
    # payload = f"{user_id}:{connection_id}"
    payload = json.dumps(
                {
                    "user_id": str(user_id),
                    "connection_id": str(connection_id),
                    "post_connect_redirect_url": post_connect_redirect_url or None,
                },
                separators=(",", ":"),
            )
    state = _state_signer.sign(payload)

    query = urlencode({
        'response_type': 'code',
        'client_id': client_id,
        'redirect_uri': redirect_uri,
        'scope': OAUTH_SCOPE,
        'state': state,
    })

    domain = netsuite_account_domain(account_id)
    return f'https://{domain}.app.netsuite.com/app/login/oauth2/authorize.nl?{query}'


# def resolve_user_id_from_state(state: str) -> tuple[str,str]:
#     """
#     Verify a `state` value's signature and age, and return the user_id it
#     encodes. Raises NetSuiteStateMismatchException if the value is
#     missing, malformed, expired, or tampered with.
#     """
#     if not state:
#         raise NetSuiteStateMismatchException('Missing OAuth state parameter.')

#     try: 
#         payload = _state_signer.unsign(
#             state,
#             max_age=STATE_MAX_AGE_SECONDS,
#         )

#         user_id, connection_id = payload.split(":", 1)

#         return user_id, connection_id
    
#     except signing.SignatureExpired as exc:

#         raise NetSuiteStateMismatchException(
#             "OAuth state has expired. Please try connecting again."
#         ) from exc
    
#     except(
#         signing.BadSignature,ValueError
#     ) as exc:
#         raise NetSuiteStateMismatchException(
#             "Invalid OAuth state parameter."
#         ) from exc

def _resolve_state_payload(state: str) -> OAuthStatePayload:
    """Verify OAuth state and decode its signed payload."""

    if not state:
        raise NetSuiteStateMismatchException(
            "Missing OAuth state parameter."
        )

    try:
        payload = _state_signer.unsign(
            state,
            max_age=STATE_MAX_AGE_SECONDS,
        )
    except signing.SignatureExpired as exc:
        raise NetSuiteStateMismatchException(
            "OAuth state has expired. Please try connecting again."
        ) from exc
    except signing.BadSignature as exc:
        raise NetSuiteStateMismatchException(
            "Invalid OAuth state parameter."
        ) from exc

    try:
        decoded = json.loads(payload)
    except json.JSONDecodeError:
        # Backward compatibility with the previous user_id:connection_id
        # payload format.
        parts = payload.split(":", 1)

        if len(parts) != 2 or not all(parts):
            raise NetSuiteStateMismatchException(
                "Invalid OAuth state parameter."
            )

        return {
            "user_id": parts[0],
            "connection_id": parts[1],
            "post_connect_redirect_url": None,
        }

    if not isinstance(decoded, dict):
        raise NetSuiteStateMismatchException(
            "Invalid OAuth state parameter."
        )

    user_id = decoded.get("user_id")
    connection_id = decoded.get("connection_id")
    redirect_url = decoded.get("post_connect_redirect_url")

    if (
        not isinstance(user_id, str)
        or not user_id
        or not isinstance(connection_id, str)
        or not connection_id
        or (
            redirect_url is not None
            and not isinstance(redirect_url, str)
        )
    ):
        raise NetSuiteStateMismatchException(
            "Invalid OAuth state payload."
        )

    return {
        "user_id": user_id,
        "connection_id": connection_id,
        "post_connect_redirect_url": redirect_url,
    }


def resolve_user_id_from_state(state: str) -> tuple[str, str]:
    """Return the user and connection IDs from a verified OAuth state."""

    payload = _resolve_state_payload(state)
    return payload["user_id"], payload["connection_id"]


def resolve_post_connect_redirect_url_from_state(
    state: str,
) -> str | None:
    """Return the optional redirect destination from verified OAuth state."""

    payload = _resolve_state_payload(state)
    return payload["post_connect_redirect_url"]
