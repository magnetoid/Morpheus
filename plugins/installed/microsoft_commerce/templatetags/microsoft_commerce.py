"""Microsoft UET (Universal Event Tracking) tag — Bing's conversion pixel.

Loads the UET tag (pageLoad auto) + fires a purchase event on the order-
confirmation page (revenue_value + currency + transaction_id = order number).
Renders nothing until a numeric UET tag id is set + enabled.

XSS-safe: tag id is digit-validated; every dynamic value is json-encoded with
`< > &` escaped to \\uXXXX.
"""

from __future__ import annotations

import json
import re

from django import template
from django.utils.safestring import mark_safe

register = template.Library()

_TAG_RE = re.compile(r'^\d{5,20}$')


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
            'revenue_value': float(amount) if amount is not None else 0.0,
            'currency': str(getattr(total, 'currency', '') or 'USD'),
            'transaction_id': onum,
        }
    except Exception:  # noqa: BLE001
        return ''
    return f'window.uetq.push("event","purchase",{_js(data)});'


@register.simple_tag(takes_context=True)
def uet_tag(context):
    """Render the Microsoft UET snippet, or '' when disabled/unconfigured."""
    from plugins.installed.microsoft_commerce.services.settings import (  # noqa: PLC0415
        microsoft_settings,
        raw_config,
    )

    if not microsoft_settings().uet_enabled:
        return ''
    tag_id = (raw_config().get('uet_tag_id') or '').strip()
    if not _TAG_RE.match(tag_id):
        return ''

    purchase = _purchase_js(context.get('order'), context.get('request'))
    snippet = (
        '<script>(function(w,d,t,r,u){var f,n,i;w[u]=w[u]||[],f=function(){'
        f'var o={{ti:{_js(tag_id)},enableAutoSpaTracking:!0}};'
        'o.q=w[u],w[u]=new UET(o),w[u].push("pageLoad")},n=d.createElement(t),n.src=r,'
        'n.async=1,n.onload=n.onreadystatechange=function(){var s=this.readyState;'
        's&&"loaded"!==s&&"complete"!==s||(f(),n.onload=n.onreadystatechange=null)},'
        'i=d.getElementsByTagName(t)[0],i.parentNode.insertBefore(n,i)})'
        '(window,document,"script","//bat.bing.com/bat.js","uetq");'
        f'{purchase}</script>'
        f'<noscript><img src="//bat.bing.com/action/0?ti={tag_id}&amp;Ver=2" '
        'height="0" width="0" style="display:none;visibility:hidden"/></noscript>'
    )
    return mark_safe(snippet)  # noqa: S308 — id digit-validated, values json+escaped
