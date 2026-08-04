"""
Standard API response builders for ERP Pulse.

Every response follows the standard envelope:

    {
        "success": true/false,
        "message": "...",
        "data": {...},
        "meta": {...}
    }

The ``meta`` key is reserved for pagination, rate-limit, or other
non-domain metadata. It defaults to an empty object so the envelope
shape is always consistent.

This module is the canonical response builder for new code. The existing
``common/utils/response.py`` (which lacks ``meta``) remains untouched
so existing imports continue to work — no existing code is modified.
"""

from rest_framework.response import Response
from rest_framework import status as http_status


def success_response(
    *,
    message: str,
    data: dict | None = None,
    meta: dict | None = None,
    status_code: int = http_status.HTTP_200_OK,
) -> Response:
    """
    Build a success envelope response.

    Parameters
    ----------
    message : str
        Human-readable success message.
    data : dict | None
        Domain payload. Defaults to ``{}`` when omitted.
    meta : dict | None
        Non-domain metadata (pagination, rate-limit info, etc.).
        Defaults to ``{}`` when omitted.
    status_code : int
        HTTP status code (default 200).
    """
    return Response(
        {
            'success': True,
            'message': message,
            'data': data if data is not None else {},
            'meta': meta if meta is not None else {},
        },
        status=status_code,
    )


def error_response(
    *,
    message: str,
    data: dict | None = None,
    meta: dict | None = None,
    errors: dict | None = None,
    status_code: int = http_status.HTTP_400_BAD_REQUEST,
) -> Response:
    """
    Build an error envelope response.

    Parameters
    ----------
    message : str
        Human-readable error message.
    data : dict | None
        Optional domain data to include (rarely used for errors).
        Defaults to ``{}`` when omitted.
    meta : dict | None
        Non-domain metadata. Defaults to ``{}`` when omitted.
    errors : dict | None
        Detailed error information (e.g., per-field validation errors).
        Defaults to ``{}`` when omitted.
    status_code : int
        HTTP status code (default 400).
    """
    return Response(
        {
            'success': False,
            'message': message,
            'data': data if data is not None else {},
            'meta': meta if meta is not None else {},
            'errors': errors if errors is not None else {},
        },
        status=status_code,
    )


def paginated_response(
    *,
    message: str,
    results: list,
    count: int,
    offset: int = 0,
    limit: int = 20,
    meta: dict | None = None,
    status_code: int = http_status.HTTP_200_OK,
) -> Response:
    """
    Build a paginated success response.

    Pagination metadata goes into ``meta`` rather than ``data`` so the
    domain payload (``results``) stays clean.

    Parameters
    ----------
    message : str
        Human-readable success message.
    results : list
        The page of items being returned.
    count : int
        Total number of items across all pages.
    offset : int
        Zero-based offset of the current page.
    limit : int
        Maximum items per page.
    meta : dict | None
        Additional non-domain metadata merged with pagination info.
    status_code : int
        HTTP status code (default 200).
    """
    pagination_meta = {
        'count': count,
        'offset': offset,
        'limit': limit,
        'has_next': offset + limit < count,
        'has_previous': offset > 0,
    }
    if meta:
        pagination_meta.update(meta)

    return Response(
        {
            'success': True,
            'message': message,
            'data': {
                'results': results,
            },
            'meta': pagination_meta,
        },
        status=status_code,
    )