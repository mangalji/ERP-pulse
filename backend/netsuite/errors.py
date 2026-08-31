"""
Maps NetSuite HTTP responses to netsuite/exceptions.py classes.

Previously this logic was duplicated three times inside client.py
(_get, _post, _post_token_request), each hand-rolling near-identical
status-code checks with slightly different messages. Centralized here
so there's one place to update if NetSuite's error shapes change, and
so client.py's methods read as "send, then interpret" rather than
each carrying its own copy of the interpretation.

Response bodies are never included in raised exception messages or
logged in full — NETSUITE_CONTEXT.md's "never log credentials" applies
broadly here since NetSuite error bodies can echo back request details.
"""

import requests
import logging
from netsuite.exceptions import (
    NetSuiteRecordFetchException,
    NetSuiteRecordNotFoundException,
    NetSuiteTokenExchangeException,
)

logger = logging.getLogger(__name__)


def raise_for_record_response(response: requests.Response, *, path: str) -> None:
    """Used by both the record GET endpoints and the generic POST (SuiteQL)."""
    if 200 <= response.status_code < 300:
        return
    try:
        payload=response.json()
    except ValueError:
        payload = None
    logger.error(
        "NetSuite API rejected request — "
        "status=%s path=%s response=%r",
        response.status_code,
        path,
        payload if payload is not None else response.text,
    )

    if isinstance(payload, dict):
        message = (
            payload.get("message")
            or payload.get("detail")
            or payload.get("o:errorCode")
            or payload.get("title")
            or str(payload)
        )
    else:
        message = response.text.strip()

    if response.status_code == 404:
        raise NetSuiteRecordNotFoundException('The requested NetSuite record was not found.')
    
    raise NetSuiteRecordFetchException(
        f"NetSuite rejected request ({response.status_code}) "
        f"for {path}: {message}"
    )


def raise_for_token_response(response: requests.Response) -> None:
    if response.ok:
        return
    try:
        payload = response.json()
    except ValueError:
        payload={}

    error_code = payload.get("error") if isinstance(payload,dict) else None

    error_description = payload.get("error_description") if isinstance(payload, dict) else None

    # OAuth authorization is no longer valid.
    # This is a permanent connection-authentication failure and must not
    # be retried with the same refresh token.

    if error_code == "invalid_grant":
        raise NetSuiteTokenExchangeException(
            "NETSUITE_INVALID_GRANT: "
            "The NetSuite refresh token is no longer valid."
        )

     # Do not expose raw OAuth response details to users.
    if error_code == "invalid_client":
        raise NetSuiteTokenExchangeException(
            "NETSUITE_INVALID_CLIENT: "
            "The NetSuite client credentials were rejected."
        )

    if error_code == "unsupported_grant_type":
        raise NetSuiteTokenExchangeException(
            "NETSUITE_UNSUPPORTED_GRANT: "
            "NetSuite rejected the OAuth grant type."
        )

    # Preserve a safe diagnostic for server-side logging/debugging.
    safe_code = str(error_code or "unknown_error")

    logger.error(
        "NetSuite token request rejected — status=%s error=%s",
        response.status_code,
        safe_code,
    )

    raise NetSuiteTokenExchangeException(
        f"NETSUITE_TOKEN_ERROR: {error_description or safe_code}"
    )
