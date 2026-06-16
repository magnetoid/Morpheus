"""TikTok Pixel (ttq) with dynamic content events.

Base pixel + page() + ViewContent on PDPs (content_id = catalog feed id) and
CompletePayment on the order-confirmation page (event_id = order_number → dedupes
against the server Events API). Renders nothing until a pixel code is set +
enabled.

XSS-safe: pixel code is regex-validated; every dynamic value is json-encoded with
`< > &` escaped to \\uXXXX.
"""

from __future__ import annotations

import contextlib
import json
import re

from django import template
from django.utils.safestring import mark_safe

register = template.Library()

_PIXEL_RE = re.compile(r'^[A-Za-z0-9]{6,40}$')


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
        rel = getattr(order, 'items', None)
        if hasattr(rel, 'all'):
            rel = list(rel.all())
        contents = []
        for line in rel or []:
            sku = (
                getattr(line, 'sku', '')
                or getattr(getattr(line, 'variant', None), 'sku', '')
                or getattr(getattr(line, 'product', None), 'sku', '')
            )
            if sku:
                contents.append(
                    {'content_id': sku, 'quantity': int(getattr(line, 'quantity', 1) or 1)}
                )
        total = getattr(order, 'total', None)
        amount = getattr(total, 'amount', None)
        data = {
            'currency': str(getattr(total, 'currency', '') or 'USD'),
            'content_type': 'product',
            'contents': contents,
        }
        if amount is not None:
            data['value'] = float(amount)
    except Exception:  # noqa: BLE001
        return ''
    return f'ttq.track("CompletePayment",{_js(data)},{{event_id:{_js(onum)}}});'


@register.simple_tag(takes_context=True)
def tiktok_pixel(context):
    """Render the TikTok Pixel snippet, or '' when disabled/unconfigured."""
    from plugins.installed.tiktok_commerce.services.api import creds  # noqa: PLC0415
    from plugins.installed.tiktok_commerce.services.settings import tiktok_settings  # noqa: PLC0415

    if not tiktok_settings().pixel_enabled:
        return ''
    code = creds()['pixel_code']
    if not _PIXEL_RE.match(code):
        return ''

    request = context.get('request')
    view_content = ''
    product = context.get('product')
    if product is not None:
        pid = getattr(product, 'sku', '') or str(getattr(product, 'id', '') or '')
        price = getattr(product, 'display_price', None) or getattr(product, 'price', None)
        amount = getattr(price, 'amount', None)
        if pid:
            params = {
                'content_id': str(pid),
                'content_type': 'product',
                'currency': str(getattr(price, 'currency', '') or 'USD'),
            }
            if amount is not None:
                with contextlib.suppress(TypeError, ValueError):
                    params['value'] = float(amount)
            view_content = f'ttq.track("ViewContent",{_js(params)});'

    purchase = _purchase_js(context.get('order'), request)
    snippet = (
        '<script>!function(w,d,t){w.TiktokAnalyticsObject=t;var ttq=w[t]=w[t]||[];'
        'ttq.methods=["page","track","identify","instances","debug","on","off","once","ready",'
        '"alias","group","enableCookie","disableCookie"];ttq.setAndDefer=function(t,e){'
        't[e]=function(){t.push([e].concat(Array.prototype.slice.call(arguments,0)))}};'
        'for(var i=0;i<ttq.methods.length;i++)ttq.setAndDefer(ttq,ttq.methods[i]);'
        'ttq.instance=function(t){for(var e=ttq._i[t]||[],n=0;n<ttq.methods.length;n++)'
        'ttq.setAndDefer(e,ttq.methods[n]);return e};ttq.load=function(e,n){'
        'var r="https://analytics.tiktok.com/i18n/pixel/events.js";ttq._i=ttq._i||{};'
        'ttq._i[e]=[];ttq._i[e]._u=r;ttq._t=ttq._t||{};ttq._t[e]=+new Date;'
        'ttq._o=ttq._o||{};ttq._o[e]=n||{};var o=d.createElement("script");'
        'o.type="text/javascript";o.async=!0;o.src=r+"?sdkid="+e+"&lib="+t;'
        'var a=d.getElementsByTagName("script")[0];a.parentNode.insertBefore(o,a)};'
        f'ttq.load({_js(code)});ttq.page();{view_content}{purchase}}}(window,document,"ttq");</script>'
    )
    return mark_safe(snippet)  # noqa: S308 — code regex-validated, values json+escaped
