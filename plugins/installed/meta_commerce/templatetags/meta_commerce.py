"""Meta Pixel (fbevents) with dynamic-ads parameters.

Emits the base pixel + a ViewContent on PDPs carrying `content_ids` (= the
catalog feed id / product SKU), `content_type=product`, value + currency — so
Advantage+ catalog (dynamic) ads and retargeting line up with the feed. Renders
nothing until a numeric pixel id is set + enabled. Obeys the tracking plugin's
Consent Mode by virtue of being a standard pixel.

XSS-safe: pixel id is digit-validated; every dynamic value is json-encoded with
`< > &` escaped to their \\uXXXX forms before reaching the page.
"""

from __future__ import annotations

import contextlib
import json
import re

from django import template
from django.utils.safestring import mark_safe

register = template.Library()

_PIXEL_RE = re.compile(r'^\d{5,20}$')


def _js(value) -> str:
    return json.dumps(value).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')


def _purchase_js(order, request) -> str:
    """Client-side Purchase fbq for the order-confirmation page, with
    eventID = order_number so it DEDUPES against the server-side CAPI Purchase
    (which uses the same id). Only fires on the /order/confirmation/ path so it
    can't misfire elsewhere. '' when not applicable."""
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
        ids, contents = [], []
        for line in rel or []:
            sku = (
                getattr(line, 'sku', '')
                or getattr(getattr(line, 'variant', None), 'sku', '')
                or getattr(getattr(line, 'product', None), 'sku', '')
            )
            if sku:
                ids.append(sku)
                contents.append({'id': sku, 'quantity': int(getattr(line, 'quantity', 1) or 1)})
        total = getattr(order, 'total', None)
        amount = getattr(total, 'amount', None)
        data = {
            'currency': str(getattr(total, 'currency', '') or 'USD'),
            'content_type': 'product',
            'content_ids': ids,
            'contents': contents,
        }
        if amount is not None:
            data['value'] = float(amount)
    except Exception:  # noqa: BLE001 — never break the page over the pixel
        return ''
    return f'fbq("track","Purchase",{_js(data)},{_js({"eventID": onum})});'


@register.simple_tag(takes_context=True)
def meta_pixel(context):
    """Render the Meta Pixel snippet, or '' when disabled/unconfigured."""
    from plugins.installed.meta_commerce.services.graph import creds  # noqa: PLC0415
    from plugins.installed.meta_commerce.services.settings import meta_settings  # noqa: PLC0415

    if not meta_settings().pixel_enabled:
        return ''
    pixel_id = creds()['pixel_id']
    if not _PIXEL_RE.match(pixel_id):
        return ''

    request = context.get('request')
    view_content = ''
    product = context.get('product')
    if product is not None:
        pid = getattr(product, 'sku', '') or str(getattr(product, 'id', '') or '')
        price = getattr(product, 'display_price', None) or getattr(product, 'price', None)
        amount = getattr(price, 'amount', None)
        currency = str(getattr(price, 'currency', '') or 'USD')
        if pid:
            params = {
                'content_ids': [str(pid)],
                'content_type': 'product',
                'currency': currency,
            }
            if amount is not None:
                with contextlib.suppress(TypeError, ValueError):
                    params['value'] = float(amount)
            view_content = f'fbq("track","ViewContent",{_js(params)});'

    purchase = _purchase_js(context.get('order'), request)

    snippet = (
        '<script>!function(f,b,e,v,n,t,s){if(f.fbq)return;n=f.fbq=function(){n.callMethod?'
        'n.callMethod.apply(n,arguments):n.queue.push(arguments)};if(!f._fbq)f._fbq=n;'
        'n.push=n;n.loaded=!0;n.version="2.0";n.queue=[];t=b.createElement(e);t.async=!0;'
        't.src=v;s=b.getElementsByTagName(e)[0];s.parentNode.insertBefore(t,s)}'
        '(window,document,"script","https://connect.facebook.net/en_US/fbevents.js");'
        f'fbq("init",{_js(pixel_id)});fbq("track","PageView");{view_content}{purchase}</script>'
        f'<noscript><img height="1" width="1" style="display:none" '
        f'src="https://www.facebook.com/tr?id={pixel_id}&amp;ev=PageView&amp;noscript=1"/></noscript>'
    )
    return mark_safe(snippet)  # noqa: S308 — id digit-validated, values json+escaped
