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

    snippet = (
        '<script>!function(f,b,e,v,n,t,s){if(f.fbq)return;n=f.fbq=function(){n.callMethod?'
        'n.callMethod.apply(n,arguments):n.queue.push(arguments)};if(!f._fbq)f._fbq=n;'
        'n.push=n;n.loaded=!0;n.version="2.0";n.queue=[];t=b.createElement(e);t.async=!0;'
        't.src=v;s=b.getElementsByTagName(e)[0];s.parentNode.insertBefore(t,s)}'
        '(window,document,"script","https://connect.facebook.net/en_US/fbevents.js");'
        f'fbq("init",{_js(pixel_id)});fbq("track","PageView");{view_content}</script>'
        f'<noscript><img height="1" width="1" style="display:none" '
        f'src="https://www.facebook.com/tr?id={pixel_id}&amp;ev=PageView&amp;noscript=1"/></noscript>'
    )
    return mark_safe(snippet)  # noqa: S308 — id digit-validated, values json+escaped
