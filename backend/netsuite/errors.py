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
from netsuite.exceptions import NetSuiteRecordFetchException,NetSuiteRecordNotFoundException,NetSuiteTokenExchangeException

def raise_for_record_exception(response: requests.Response,*,path:str)->None:
    """Used by both the record GET endpoints and the generic POST (SuiteQL)."""
    if response.status_code == 404:
        raise NetSuiteRecordNotFoundException('The requested NetSuite record was not found.')
    if not response.ok:
        raise NetSuiteRecordFetchException(
            'NetSuite rejected the record request. Please reconnect your account.'
        )

def raise_for_token_response(response: requests.Response) -> None:
    if not response.ok:
        raise NetSuiteTokenExchangeException(
            'NetSuite rejected the authentication request. Please reconnect your account.'
        )