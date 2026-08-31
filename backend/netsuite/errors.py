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
    if not response.ok:
        raise NetSuiteTokenExchangeException(
            'NetSuite rejected the authentication request. Please reconnect your account.'
        )
