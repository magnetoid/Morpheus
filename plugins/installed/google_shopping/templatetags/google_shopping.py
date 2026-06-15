"""Google Ads dynamic remarketing tag (gtag) for the storefront.

Emits the Google Ads remarketing event with `ecomm_prodid` / `ecomm_pagetype` /
`ecomm_totalvalue` so Shopping / Performance Max can build remarketing audiences
and show dynamic product ads. The product id matches the Merchant feed `g:id`
(the product SKU), so audiences line up with the feed.

This is the REMARKETING tag only — the conversion pixel stays in the `tracking`
plugin. Consent: the tag uses gtag, so it obeys the Consent Mode v2 defaults
that the tracking plugin sets in <head> (ad_storage), with no extra coupling.

XSS-safe: the conversion id is regex-validated (AW-…) and every dynamic value is
serialised through json.dumps before it reaches the page.
"""

from __future__ import annotations

import contextlib
import json
import re

from django import template
from django.utils.safestring import mark_safe

register = template.Library()

_AW_RE = re.compile(r'^AW-[A-Za-z0-9]+$')

# Ordered prefix → Google ecomm_pagetype. A bare /products/<slug>/ is a product
# page; the /products listing and the taxonomy pages are category pages.
_PAGETYPE_RULES = (
    ('/products/', 'product'),
    ('/products', 'category'),
    ('/genre/', 'category'),
    ('/topic/', 'category'),
    ('/cart', 'cart'),
    ('/checkout', 'purchase'),
    ('/search', 'searchresults'),
)


def _pagetype(request) -> str:
    path = getattr(request, 'path', '') or ''
    if path == '/':
        return 'home'
    for prefix, kind in _PAGETYPE_RULES:
        if path.startswith(prefix):
            return kind
    return 'other'


@register.simple_tag(takes_context=True)
def gads_remarketing(context):
    """Render the Google Ads dynamic-remarketing snippet, or '' when disabled."""
    from plugins.installed.google_shopping.services.settings import feed_settings  # noqa: PLC0415

    s = feed_settings()
    cid = (s.remarketing_id or '').strip()
    if not s.remarketing_enabled or not _AW_RE.match(cid):
        return ''

    request = context.get('request')
    params: dict = {'ecomm_pagetype': _pagetype(request)}

    product = context.get('product')
    if product is not None:
        pid = getattr(product, 'sku', '') or str(getattr(product, 'id', '') or '')
        if pid:
            params['ecomm_prodid'] = str(pid)
        price = getattr(product, 'display_price', None) or getattr(product, 'price', None)
        amount = getattr(price, 'amount', None)
        if amount is not None:
            with contextlib.suppress(TypeError, ValueError):
                params['ecomm_totalvalue'] = float(amount)

    # json.dumps does NOT escape < > & — a product SKU like "</script>…" would
    # break out of this inline <script>. Escape them to their \uXXXX forms (the
    # standard JSON-in-HTML defence) before emission.
    def _js(value) -> str:
        return (
            json.dumps(value)
            .replace('<', '\\u003c')
            .replace('>', '\\u003e')
            .replace('&', '\\u0026')
        )

    cid_js = _js(cid)
    params_js = _js(params)
    snippet = (
        f'<script async src="https://www.googletagmanager.com/gtag/js?id={cid}"></script>'
        '<script>window.dataLayer=window.dataLayer||[];'
        'function gtag(){dataLayer.push(arguments);}'
        f'gtag("js",new Date());gtag("config",{cid_js});'
        f'gtag("event","page_view",{params_js});</script>'
    )
    return mark_safe(snippet)  # noqa: S308 — id regex-validated, values json-encoded
