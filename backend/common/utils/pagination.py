"""
Standard paginated API response builder.

Wraps the standard success_response envelope with pagination metadata,
so list endpoints return a consistent shape:

    {
        "success": true,
        "message": "...",
        "data": {
            "count": 100,
            "next": "https://.../api/v1/.../?offset=20&limit=20",
            "previous": null,
            "results": [...]
        }
    }
"""

from math import ceil

from django.conf import settings
from rest_framework.request import Request

from common.utils.response import success_response


def paginated_response(
    *,
    message: str,
    results: list,
    count: int,
    request: Request,
    offset: int = 0,
    limit: int = 20,
    status_code: int = 200,
) -> dict:
    """
    Build a paginated success response.

    Parameters
    ----------
    message : str
        Human-readable success message.
    results : list
        The page of items being returned.
    count : int
        Total number of items across all pages (not just this page).
    request : Request
        The DRF request — used to reconstruct full URLs for next/previous.
    offset : int
        Zero-based offset of the current page.
    limit : int
        Maximum items per page.
    status_code : int
        HTTP status code (default 200).

    Returns
    -------
    Response
        DRF Response with the standard success envelope containing
        pagination metadata.
    """

    def _build_url(new_offset: int) -> str | None:
        """Build a full URL for the given offset, preserving other query params."""
        if new_offset < 0 or new_offset >= count:
            return None
        params = request.query_params.copy()
        params["offset"] = str(new_offset)
        params["limit"] = str(limit)
        return request.build_absolute_uri(
            f"{request.path}?{params.urlencode()}"
        )

    previous_offset = offset - limit
    next_offset = offset + limit

    return success_response(
        message=message,
        data={
            "count": count,
            "next": _build_url(next_offset),
            "previous": _build_url(previous_offset),
            "results": results,
        },
        status_code=status_code,
    )
