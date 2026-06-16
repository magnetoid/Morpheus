"""Pinterest Tag (pintrk) with dynamic events.

Base tag + page() + a pagevisit on PDPs (product_id = catalog feed id) and
checkout on the order-confirmation page (event_id = order_number → dedupes
against the server Conversions API). Renders nothing until a numeric tag id is
set + enabled.

XSS-safe: tag id is digit-validated; every dynamic value is json-encoded with
`< > &` escaped to \\uXXXX.
"""

from __future__ import annotations

import contextlib
import json
import re

from django import template
from django.utils.safestring import mark_safe

register = template.Library()

_TAG_RE = re.compile(r'^\d{6,20}$')


def _js(value) -> str:
    return json.dumps(value).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')


def _checkout_js(order, request) -> str:
    if order is None:
        return ''
    if not (getattr(request, 'path', '') or '').startswith('/order/confirmation/'):
        return ''
    onum = str(getattr(order, 'order_number', '') or '')
    if not onum:
        return ''
    try:
        rel = getattr(order, 'items', None)
        if hasattr(rel, 'all'):
            rel = list(rel.all())
        line_items = []
        for line in rel or []:
            sku = (
                getattr(line, 'sku', '')
                or getattr(getattr(line, 'variant', None), 'sku', '')
                or getattr(getattr(line, 'product', None), 'sku', '')
            )
            if sku:
                line_items.append(
                    {'product_id': sku, 'quantity': int(getattr(line, 'quantity', 1) or 1)}
                )
        total = getattr(order, 'total', None)
        amount = getattr(total, 'amount', None)
        data = {
            'currency': str(getattr(total, 'currency', '') or 'USD'),
            'order_id': onum,
            'line_items': line_items,
        }
        if amount is not None:
            data['value'] = float(amount)
    except Exception:  # noqa: BLE001
        return ''
    return f'pintrk("track","checkout",{_js(data)},{{event_id:{_js(onum)}}});'


@register.simple_tag(takes_context=True)
def pinterest_tag(context):
    """Render the Pinterest Tag snippet, or '' when disabled/unconfigured."""
    from plugins.installed.pinterest_commerce.services.api import creds  # noqa: PLC0415
    from plugins.installed.pinterest_commerce.services.settings import (
        pinterest_settings,  # noqa: PLC0415
    )

    if not pinterest_settings().tag_enabled:
        return ''
    tag_id = creds()['tag_id']
    if not _TAG_RE.match(tag_id):
        return ''

    request = context.get('request')
    page_visit = ''
    product = context.get('product')
    if product is not None:
        pid = getattr(product, 'sku', '') or str(getattr(product, 'id', '') or '')
        price = getattr(product, 'display_price', None) or getattr(product, 'price', None)
        amount = getattr(price, 'amount', None)
        if pid:
            data = {
                'line_items': [{'product_id': str(pid)}],
                'currency': str(getattr(price, 'currency', '') or 'USD'),
            }
            if amount is not None:
                with contextlib.suppress(TypeError, ValueError):
                    data['value'] = float(amount)
            page_visit = f'pintrk("track","pagevisit",{_js(data)});'

    checkout = _checkout_js(context.get('order'), request)
    snippet = (
        '<script>!function(e){if(!window.pintrk){window.pintrk=function(){'
        'window.pintrk.queue.push(Array.prototype.slice.call(arguments))};var n=window.pintrk;'
        'n.queue=[],n.version="3.0";var t=document.createElement("script");t.async=!0,t.src=e;'
        'var r=document.getElementsByTagName("script")[0];r.parentNode.insertBefore(t,r)}}'
        '("https://s.pinimg.com/ct/core.js");'
        f'pintrk("load",{_js(tag_id)});pintrk("page");{page_visit}{checkout}</script>'
        f'<noscript><img height="1" width="1" style="display:none" alt="" '
        f'src="https://ct.pinterest.com/v3/?event=init&amp;tid={tag_id}&amp;noscript=1"/></noscript>'
    )
    return mark_safe(snippet)  # noqa: S308 — id digit-validated, values json+escaped
