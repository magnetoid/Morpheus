"""Pagination policy: page 2 is a page, page 1 is the category, page 900 is not.

Pagination is the one place where near-duplicate URLs are *supposed* to exist,
so it gets its own policy rather than an `IndexRule` row. Three decisions:

* **`?page=2` is self-canonical and indexable.** Canonicalising it onto page 1
  is the classic mistake — it tells an engine that every product past the first
  screen does not have a home.
* **`?page=1` redirects to the clean URL.** It is the same page under a second
  name; a canonical would paper over it, a 301 removes it.
* **A page number past the end is a 404.** This is the one that was costing
  something: Django's paginator clamps out-of-range numbers back to page 1, so
  `?page=999` returned 200 with page 1's products *and a canonical naming
  itself* — an unbounded family of indexable duplicates, one per integer, all
  claiming to be the original. Out of range is not a page.
"""

from __future__ import annotations

from urllib.parse import parse_qsl, urlencode


def page_number(page_obj) -> int:
    """The 1-based number of a Django paginator page, or 0 if there isn't one."""
    try:
        return int(getattr(page_obj, 'number', 0) or 0)
    except (TypeError, ValueError):
        return 0


def page_value(raw) -> int:
    """The page number a paginator would read from `?page=`, or 0 if it isn't one.

    Numeric, not textual: `Paginator.page()` does `int(value)`, so `?page=01`
    and `?page=+1` both render page 1. Comparing the raw string would let those
    spellings keep a canonical of their own — a second address for the first
    page of a listing, which is the shape of duplicate this module exists to
    remove.
    """
    try:
        return int(str(raw).strip())
    except (TypeError, ValueError):
        return 0


def page_one_redirect_target(request) -> str:
    """Where `?page=1` should go — or `''` when this URL is fine as it is.

    Preserves the rest of the query string verbatim (order included): this is a
    redirect a person follows, not a canonical, and reordering a merchant's
    campaign parameters on the way through would be a gratuitous difference
    between the link they shared and the one the browser lands on.
    """
    if request is None or getattr(request, 'method', 'GET') != 'GET':
        return ''
    try:
        values = request.GET.getlist('page')
    except Exception:  # noqa: BLE001 — a request-like object without a QueryDict
        return ''
    # An empty `?page=` and every spelling of 1 collapse; anything that is not a
    # page number is left alone so the view can 404 it.
    if not values or any(str(v).strip() != '' and page_value(v) != 1 for v in values):
        return ''

    query = request.META.get('QUERY_STRING', '') or ''
    rest = [(k, v) for k, v in parse_qsl(query, keep_blank_values=True) if k.lower() != 'page']
    path = request.path or '/'
    return f'{path}?{urlencode(rest)}' if rest else path


def paginated_title(title: str, page_obj) -> str:
    """Give page 2 onwards a title of its own.

    Every page of a listing otherwise carries the category's title, so an engine
    sees a dozen identically-titled pages and picks one — usually not the one a
    given product is on. Page 1 is left alone: it *is* the category.
    """
    number = page_number(page_obj)
    if number < 2 or not title:
        return title
    return f'{title} — Page {number}'
