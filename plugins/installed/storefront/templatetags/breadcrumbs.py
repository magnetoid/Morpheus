"""`{% breadcrumb_trail %}` — the visible trail, from the same list as the BreadcrumbList.

The head builds the page's BreadcrumbList from the view's `breadcrumb_items`
(seo/schema/graph.py: items with a name, moved into the page's language tree).
This tag hands the partial exactly those items, with the same urls, so the trail
a shopper sees and the one Google reads cannot disagree. A theme restyles the
trail by overriding `storefront/_breadcrumb_trail.html`; it never builds its own.

Links are written site-relative when they name this store, so a theme's markup
stays as it was (`href="/products/"`); the structured data keeps them absolute.
"""

from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit

from django import template

register = template.Library()


def _items(context) -> list[dict]:
    items = [
        {'name': str(i.get('name')), 'url': str(i.get('url') or '')}
        for i in (context.get('breadcrumb_items') or [])
        if isinstance(i, dict) and i.get('name')
    ]
    request = context.get('request')
    if request is None or not items:
        return items
    from core.i18n_links import localize_url, page_language  # noqa: PLC0415

    language = page_language(request)
    try:
        host = request.get_host()
    except Exception:  # noqa: BLE001 — a disallowed host: leave the urls as they are
        return items
    out = []
    for item in items:
        url = localize_url(item['url'], language, host) if language else item['url']
        out.append({**item, 'url': url, 'href': _site_relative(url, host)})
    return out


def _site_relative(url: str, host: str) -> str:
    parts = urlsplit(url)
    if parts.scheme in ('http', 'https') and parts.netloc.lower() == host.lower():
        return urlunsplit(('', '', parts.path or '/', parts.query, parts.fragment))
    return url


@register.inclusion_tag('storefront/_breadcrumb_trail.html', takes_context=True)
def breadcrumb_trail(context, variant: str = ''):
    """The page's trail; `variant` names a theme's alternative look (e.g. "hero")."""
    items = _items(context)
    for item in items:
        item.setdefault('href', item['url'])
    return {'breadcrumb_items': items, 'breadcrumb_variant': variant}
