"""
Pagination helper for NetSuite REST Record collection responses.

NetSuite's REST Record API collection endpoints (GET /record/v1/{type})
return a shape like:
    {"items": [...], "count": N, "hasMore": bool, "offset": N, "totalResults": N}
This walks `hasMore`/`offset` to fetch every page instead of just one.

Not yet wired into NetSuiteDataService.get_records() — that method's
existing single-page-passthrough behavior is a public API contract the
frontend already depends on (paged list views), and changing its return
shape is out of scope for this task. This helper exists for callers that
genuinely need "every record" — the Sync Manager (sync/services.py) is
the first consumer.
"""

from typing import Callable, Iterator

DEFAULT_PAGE_SIZE = 100
# Safety cap against an infinite loop if NetSuite's hasMore/offset ever
# behaves unexpectedly (e.g. never flips to False) — 100 pages at the
# default page size covers 10,000 records, which comfortably exceeds
# what a sync job should pull in one run without deliberately raising it.
MAX_PAGES = 100


def iter_all_pages(
    fetch_page: Callable[[int], dict],
    *,
    page_size: int = DEFAULT_PAGE_SIZE,
    max_pages: int = MAX_PAGES,
) -> Iterator[dict]:
    """
    fetch_page(offset) -> one page dict in the {"items": [...], "hasMore": bool, ...} shape.

    Yields each item across all pages in order, stopping when hasMore is
    falsy or max_pages is reached (whichever comes first).
    """
    offset = 0
    pages_fetched = 0

    while pages_fetched < max_pages:
        page = fetch_page(offset)
        items = page.get('items', [])
        yield from items

        pages_fetched += 1
        if not page.get('hasMore'):
            return

        # Advance by however many items this page actually returned, not
        # blindly by page_size — protects against a final partial page.
        offset += page.get('count') or len(items) or page_size
