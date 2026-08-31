"""
Generic HTTP sending layer for netsuite/client.py.

Owns: request timeout (centralized here instead of duplicated across
client.py's _get/_post/_post_token_request), correlation-ID header
injection, and retry-with-backoff for retryable calls.

client.py still builds each request (URL, headers, body) and decides
whether a given call is safe to retry — this module only knows how to
send and, when told to, retry. It has no NetSuite-specific knowledge
(no knowledge of tokens, records, or SuiteQL).

retryable=True must only be used for idempotent calls (GET record
fetches, SuiteQL reads). It must never be used for the OAuth token
endpoint (exchange_code_for_tokens/refresh_access_token) — an
authorization `code` is single-use, so retrying that POST after a
transient failure would send an already-invalidated code and fail
differently than the original error, hiding the real problem.
"""

import logging
import time
import uuid

import requests

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT_SECONDS = 15

# NetSuite record CREATE/UPDATE calls can trigger server-side workflows,
# SuiteScripts, and mandatory-field calculations (subsidiary/tax/line
# processing) — this is routinely much slower than a read, especially on
# sandbox accounts. A 15s timeout was observed timing out real, valid
# Vendor Bill creates that NetSuite was still processing. Mutating calls
# get a longer budget; nothing here makes them retryable — retryable
# stays governed by the `retryable` flag, unrelated to timeout length.
WRITE_TIMEOUT_SECONDS = 55
MAX_RETRIES = 2
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
BACKOFF_BASE_SECONDS = 0.5


def new_correlation_id() -> str:
    return uuid.uuid4().hex


def send(
    method: str,
    url: str,
    *,
    headers: dict | None = None,
    params: dict | None = None,
    data=None,
    json=None,
    auth=None,
    retryable: bool = False,
    correlation_id: str | None = None,
    timeout: int | None = None,
) -> requests.Response:
    """
    Send one HTTP request, tagged with a correlation ID header, retrying
    on 429/5xx (and on transport-level failures) when retryable=True.

    `timeout` overrides the default REQUEST_TIMEOUT_SECONDS for this call
    (e.g. WRITE_TIMEOUT_SECONDS for a record create/update, which can
    legitimately take longer than a read).

    Raises requests.RequestException on transport failure (connection
    error, timeout) exactly like a bare `requests.request()` call would —
    callers keep their existing `except requests.RequestException` blocks
    unchanged; retries just happen transparently before that.
    """
    correlation_id = correlation_id or new_correlation_id()
    request_headers = dict(headers or {})
    request_headers.setdefault('X-Correlation-Id', correlation_id)
    effective_timeout = timeout or REQUEST_TIMEOUT_SECONDS

    attempt = 0
    while True:
        attempt += 1
        try:
            response = requests.request(
                method,
                url,
                headers=request_headers,
                params=params,
                data=data,
                json=json,
                auth=auth,
                timeout=effective_timeout,
            )
        except requests.RequestException:
            if retryable and attempt <= MAX_RETRIES:
                _wait(attempt, correlation_id)
                continue
            raise

        if retryable and response.status_code in RETRYABLE_STATUS_CODES and attempt <= MAX_RETRIES:
            _wait(attempt, correlation_id, retry_after=response.headers.get('Retry-After'))
            continue

        return response


def _wait(attempt: int, correlation_id: str, retry_after: str | None = None) -> None:
    delay = _parse_retry_after(retry_after) or BACKOFF_BASE_SECONDS * (2 ** (attempt - 1))
    logger.warning(
        'Retrying NetSuite request (attempt %s, correlation_id=%s) after %.2fs.',
        attempt, correlation_id, delay,
    )
    time.sleep(delay)


def _parse_retry_after(retry_after: str | None) -> float | None:
    if not retry_after:
        return None
    try:
        return float(retry_after)
    except (TypeError, ValueError):
        # Retry-After can also be an HTTP date per RFC 9110 — not parsed
        # here (NetSuite has not been confirmed to send that form); falls
        # back to exponential backoff instead of failing the request.
        return None