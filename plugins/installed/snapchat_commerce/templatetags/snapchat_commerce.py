"""Snapchat Pixel (snaptr) with dynamic content events.

Base pixel + PAGE_VIEW + VIEW_CONTENT on PDPs (item_ids = catalog feed id) and
PURCHASE on the order-confirmation page (transaction_id = order_number → dedupes
against the server Conversions API). Renders nothing until a pixel id is set +
enabled.

XSS-safe: pixel id is regex-validated; every dynamic value is json-encoded with
`< > &` escaped to \\uXXXX.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import re

from django import template
from django.utils.safestring import mark_safe

register = template.Library()

_PIXEL_RE = re.compile(r'^[A-Za-z0-9-]{6,64}$')


def _js(value) -> str:
    return json.dumps(value).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')


def _sha256(value: str) -> str:
    return hashlib.sha256((value or '').strip().lower().encode('utf-8')).hexdigest()


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
        item_ids = []
        for line in rel or []:
            sku = (
                getattr(line, 'sku', '')
                or getattr(getattr(line, 'variant', None), 'sku', '')
                or getattr(getattr(line, 'product', None), 'sku', '')
            )
            if sku:
                item_ids.append(sku)
        total = getattr(order, 'total', None)
        amount = getattr(total, 'amount', None)
        data = {
            'currency': str(getattr(total, 'currency', '') or 'USD'),
            'item_ids': item_ids,
            'number_items': len(item_ids),
            'transaction_id': onum,
        }
        if amount is not None:
            data['price'] = float(amount)
    except Exception:  # noqa: BLE001
        return ''
    return f"snaptr('track','PURCHASE',{_js(data)});"


@register.simple_tag(takes_context=True)
def snap_pixel(context):
    """Render the Snap Pixel snippet, or '' when disabled/unconfigured."""
    from plugins.installed.snapchat_commerce.services.api import creds  # noqa: PLC0415
    from plugins.installed.snapchat_commerce.services.settings import (  # noqa: PLC0415
        snapchat_settings,
    )

    if not snapchat_settings().pixel_enabled:
        return ''
    pixel_id = creds()['pixel_id']
    if not _PIXEL_RE.match(pixel_id):
        return ''

    request = context.get('request')

    init = {}
    user = getattr(request, 'user', None)
    if user is not None and getattr(user, 'is_authenticated', False):
        email = getattr(user, 'email', '') or ''
        if email:
            init['user_email'] = _sha256(email)
    init_arg = f',{_js(init)}' if init else ''

    view_content = ''
    product = context.get('product')
    if product is not None:
        pid = getattr(product, 'sku', '') or str(getattr(product, 'id', '') or '')
        price = getattr(product, 'display_price', None) or getattr(product, 'price', None)
        amount = getattr(price, 'amount', None)
        if pid:
            params = {
                'item_ids': [str(pid)],
                'item_category': 'product',
                'currency': str(getattr(price, 'currency', '') or 'USD'),
            }
            if amount is not None:
                with contextlib.suppress(TypeError, ValueError):
                    params['price'] = float(amount)
            view_content = f"snaptr('track','VIEW_CONTENT',{_js(params)});"

    purchase = _purchase_js(context.get('order'), request)
    snippet = (
        '<script>(function(e,t,n){if(e.snaptr)return;var a=e.snaptr=function()'
        '{a.handleRequest?a.handleRequest.apply(a,arguments):a.queue.push(arguments)};'
        'a.queue=[];var s="script";var r=t.createElement(s);r.async=!0;'
        'r.src=n;var u=t.getElementsByTagName(s)[0];'
        'u.parentNode.insertBefore(r,u)})(window,document,'
        '"https://sc-static.net/scevent.min.js");'
        f"snaptr('init',{_js(pixel_id)}{init_arg});"
        f"snaptr('track','PAGE_VIEW');{view_content}{purchase}</script>"
    )
    return mark_safe(snippet)  # noqa: S308 — id regex-validated, values json+escaped
