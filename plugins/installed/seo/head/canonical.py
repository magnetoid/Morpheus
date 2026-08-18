"""Canonical URLs and the query-parameter policy.

Two knobs, both merchant-facing:

* ``canonical_strip_query_params`` (default on) drops marketing and facet
  parameters from the canonical, so `?utm_source=…`, `?fbclid=…` and
  `?sort=price` all consolidate into the clean URL.
* ``SiteSeoSettings.noindex_query_params`` names the parameters whose presence
  should ALSO make the page `noindex, follow` — the faceted-navigation lever.

Pagination is the deliberate exception: `?page=2` stays in the canonical, because
Google's guidance is that each page of a sequence self-canonicalises (canonical
to page 1 de-indexes everything past it). `?page=1` collapses to the clean URL.
"""

from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


def canonical_for(request) -> tuple[str, list[str]]:
    """Return ``(canonical_url, blocked_params_present)``."""
    if request is None:
        return '', []
    try:
        absolute = request.build_absolute_uri()
    except Exception:  # noqa: BLE001
        return '', []

    parts = urlsplit(absolute)
    if not parts.query:
        return absolute, []

    strip_all = _strip_all()
    blocklist = _blocklist()
    pairs = parse_qsl(parts.query, keep_blank_values=True)
    blocked = sorted({key for key, _ in pairs if key in blocklist})

    if strip_all:
        kept = [(k, v) for k, v in pairs if k == 'page' and v not in ('', '1')]
    elif blocklist:
        kept = [(k, v) for k, v in pairs if k not in blocklist]
    else:
        return absolute, blocked

    return urlunsplit(parts._replace(query=urlencode(kept))), blocked


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
        return urlunsplit(parts._replace(query=urlencode([*base, ('page', str(number))])))

    out: dict[str, str] = {}
    try:
        if page_obj.has_previous():
            out['prev'] = href(page_obj.previous_page_number())
        if page_obj.has_next():
            out['next'] = href(page_obj.next_page_number())
    except (AttributeError, TypeError):
        return {}
    return out


def _strip_all() -> bool:
    try:
        from plugins.installed.seo.services import _seo_plugin_cfg

        cfg = _seo_plugin_cfg()
        return bool(cfg.get('canonical_strip_query_params', True)) if cfg else True
    except Exception:  # noqa: BLE001
        return True


def _blocklist() -> set[str]:
    try:
        from plugins.installed.seo.services import site_settings

        return {str(p).strip() for p in (site_settings().noindex_query_params or []) if p}
    except Exception:  # noqa: BLE001
        return set()
