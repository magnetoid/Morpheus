"""Reddit Pixel (rdt) with dynamic events.

Base pixel + PageVisit + ViewContent on PDPs + Purchase on the order-confirmation
page (conversionId = order_number → dedupes against the server Conversions API).
Renders nothing until a pixel id is set + enabled.

XSS-safe: pixel id is regex-validated; every dynamic value json-encoded with
`< > &` escaped to \\uXXXX.
"""

from __future__ import annotations

import contextlib
import json
import re

from django import template
from django.utils.safestring import mark_safe

register = template.Library()

_PIXEL_RE = re.compile(r'^[A-Za-z0-9_]{4,50}$')


def _js(value) -> str:
    return json.dumps(value).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')


def _purchase_js(order, request) -> str:
    if order is None:
        return ''
    if not (getattr(request, 'path', '') or '').startswith('/order/confirmation/'):
        return ''
    onum = str(getattr(order, 'order_number', '') or '')
    if not onum:
        return ''
    try:
        total = getattr(order, 'total', None)
        amount = getattr(total, 'amount', None)
        data = {
            'currency': str(getattr(total, 'currency', '') or 'USD'),
            'conversionId': onum,
        }
        if amount is not None:
            data['value'] = float(amount)
    except Exception:  # noqa: BLE001
        return ''
    return f'rdt("track","Purchase",{_js(data)});'


@register.simple_tag(takes_context=True)
def reddit_pixel(context):
    """Render the Reddit Pixel snippet, or '' when disabled/unconfigured."""
    from plugins.installed.reddit_ads.services.api import creds  # noqa: PLC0415
    from plugins.installed.reddit_ads.services.settings import pixel_enabled  # noqa: PLC0415

    if not pixel_enabled():
        return ''
    pid = creds()['pixel_id']
    if not _PIXEL_RE.match(pid):
        return ''

    request = context.get('request')
    view_content = ''
    product = context.get('product')
    if product is not None:
        sku = getattr(product, 'sku', '') or str(getattr(product, 'id', '') or '')
        price = getattr(product, 'display_price', None) or getattr(product, 'price', None)
        amount = getattr(price, 'amount', None)
        if sku:
            params = {
                'products': [{'id': str(sku)}],
                'currency': str(getattr(price, 'currency', '') or 'USD'),
            }
            if amount is not None:
                with contextlib.suppress(TypeError, ValueError):
                    params['value'] = float(amount)
            view_content = f'rdt("track","ViewContent",{_js(params)});'

    purchase = _purchase_js(context.get('order'), request)
    snippet = (
        '<script>!function(w,d){if(!w.rdt){var p=w.rdt=function(){'
        'p.sendEvent?p.sendEvent.apply(p,arguments):p.callQueue.push(arguments)};'
        'p.callQueue=[];var t=d.createElement("script");t.src="https://www.redditstatic.com/ads/pixel.js",'
        't.async=!0;var s=d.getElementsByTagName("script")[0];s.parentNode.insertBefore(t,s)}}'
        '(window,document);'
        f'rdt("init",{_js(pid)});rdt("track","PageVisit");{view_content}{purchase}</script>'
    )
    return mark_safe(snippet)  # noqa: S308 — id regex-validated, values json+escaped
