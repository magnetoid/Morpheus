"""Canonical URLs — the query-parameter policy applied to a request.

The policy itself lives in `seo/rules/params.py` (one `IndexRule` row per
parameter, four policies), because robots.txt and the dashboard's URL preview
need the same answers this does. This module is the thin part: turn a request
into an absolute URL, hand the query string to the engine, put the result back
together.

Pagination is the deliberate exception to parameter handling: `?page=2` stays in
the canonical, because each page of a sequence self-canonicalises (canonical to
page 1 de-indexes everything past it). `?page=1` collapses to the clean URL —
and, since v0.50, redirects there outright.
"""

from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from plugins.installed.seo.rules import decide_params, page_number


def canonical_for(request, page_obj=None) -> tuple[str, list[str]]:
    """Return ``(canonical_url, params_holding_this_page_back)``.

    `page_obj` is the view's paginator page, when it has one. Without a real
    paginator `?page=` is treated as any other unrecognised parameter and
    dropped — otherwise a listing that shows everything on one screen publishes
    a distinct self-canonical page for every integer anyone ever appends.
    """
    if request is None:
        return '', []
    try:
        absolute = request.build_absolute_uri()
    except Exception:  # noqa: BLE001
        return '', []

    parts = urlsplit(absolute)
    if not parts.query:
        return absolute, []

    decision = decide_params(parts.query, paginated=page_number(page_obj) > 0)
    canonical = urlunsplit(parts._replace(query=decision.query))
    return canonical, list(decision.noindex_params)


def paginated_links(request, page_obj) -> dict[str, str]:
    """`rel=prev` / `rel=next` hrefs for a Django paginator page.

    Google stopped using these in 2019; Bing still reads them as sequence hints,
    and they cost one line each — so they stay.
    """
    if request is None or page_obj is None:
        return {}
    try:
        parts = urlsplit(request.build_absolute_uri())
    except Exception:  # noqa: BLE001
        return {}
    base = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k != 'page']

    def href(number: int) -> str:
        # Page 1 is the clean URL — `?page=1` 301s there, and a `rel=prev`
        # naming a URL we immediately redirect away from is a wasted hop for
        # every crawler that follows it.
        pairs = base if number == 1 else [*base, ('page', str(number))]
        return urlunsplit(parts._replace(query=urlencode(pairs)))

    out: dict[str, str] = {}
    try:
        if page_obj.has_previous():
            out['prev'] = href(page_obj.previous_page_number())
        if page_obj.has_next():
            out['next'] = href(page_obj.next_page_number())
    except (AttributeError, TypeError):
        return {}
    return out
