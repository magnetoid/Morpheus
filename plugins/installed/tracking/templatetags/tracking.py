"""Template tags for the storefront integration.

Three tags do the heavy lifting in `base.html`:

    {% load tracking %}
    ...
    <head>
      {% gtm_consent_default %}  {# emits gtag('consent','default',{...}) — must run first #}
      {% gtm_head %}             {# the GTM container snippet — only if configured #}
    </head>
    <body>
      {% gtm_noscript_body %}
      ...

Plus per-event dataLayer push partials surfaced as `{% dl_view_item product %}`
etc. — these include a small template that prepends `dataLayer.push({ecommerce: null})`
to prevent items leaking between events (the #1 production bug per the
2026 research).
"""
from __future__ import annotations

import json
from typing import Any

from django import template
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe

register = template.Library()


def _settings():
    from plugins.installed.tracking.models import TrackingSettings
    try:
        return TrackingSettings.get_solo()
    except Exception:  # noqa: BLE001 — table missing pre-migration
        return None


@register.simple_tag
def gtm_consent_default():
    """Emit Consent Mode v2 defaults **before** any GTM/gtag boot.

    Per Google's spec, defaults MUST set before the container loads
    or the page silently runs with implicit `granted` for the
    measurement window, breaking EEA compliance.
    """
    s = _settings()
    if s is None or not s.client_side_enabled:
        return ''
    default = s.consent_default or {}
    # Always emit even when the container ID is empty — the page
    # might be using server-side only + a custom gtag elsewhere.
    return mark_safe(
        '<script>window.dataLayer=window.dataLayer||[];'
        'function gtag(){dataLayer.push(arguments);}'
        f'gtag("consent","default",{json.dumps(default)});'
        '</script>'
    )


@register.simple_tag
def gtm_head():
    """Emit the GTM head snippet. No-op when GTM container is not
    configured OR client-side firing is off."""
    s = _settings()
    if s is None or not s.client_side_enabled or not s.gtm_container_id:
        return ''
    gtm = s.gtm_container_id
    return mark_safe(
        "<script>"
        "(function(w,d,s,l,i){w[l]=w[l]||[];w[l].push({'gtm.start':"
        "new Date().getTime(),event:'gtm.js'});var f=d.getElementsByTagName(s)[0],"
        "j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;"
        "j.src='https://www.googletagmanager.com/gtm.js?id='+i+dl;"
        "f.parentNode.insertBefore(j,f);"
        f"}})(window,document,'script','dataLayer','{gtm}');"
        "</script>"
    )


@register.simple_tag
def gtm_noscript_body():
    """Emit the immediate-after-`<body>` noscript fallback iframe."""
    s = _settings()
    if s is None or not s.client_side_enabled or not s.gtm_container_id:
        return ''
    gtm = s.gtm_container_id
    return mark_safe(
        f'<noscript><iframe src="https://www.googletagmanager.com/ns.html?id={gtm}" '
        'height="0" width="0" style="display:none;visibility:hidden"></iframe></noscript>'
    )


def _datalayer_push(event_name: str, ecommerce: dict[str, Any]) -> str:
    """Render a dataLayer.push() pair with the mandatory ecommerce-null reset."""
    s = _settings()
    if s is None or not s.client_side_enabled:
        return ''
    if not s.event_enabled(event_name):
        return ''
    body = json.dumps({'event': event_name, 'ecommerce': ecommerce})
    return mark_safe(
        '<script>'
        'window.dataLayer=window.dataLayer||[];'
        'dataLayer.push({ecommerce:null});'
        f'dataLayer.push({body});'
        '</script>'
    )


@register.simple_tag
def dl_view_item(product):
    """`view_item` dataLayer push for the PDP."""
    if not product:
        return ''
    from plugins.installed.tracking.services.event_mapping import view_item
    try:
        _, params = view_item(product)
    except Exception:  # noqa: BLE001
        return ''
    ecommerce = {
        'currency': params.get('currency', 'USD'),
        'value': params.get('value', 0),
        'items': params.get('items', []),
    }
    return _datalayer_push('view_item', ecommerce)


@register.simple_tag
def dl_view_item_list(items, list_id: str = '', list_name: str = ''):
    """`view_item_list` push for the PLP / category page."""
    if not items:
        return ''
    from plugins.installed.tracking.services.event_mapping import view_item_list
    try:
        _, params = view_item_list(items=list(items), list_id=list_id, list_name=list_name)
    except Exception:  # noqa: BLE001
        return ''
    ecommerce = {
        'item_list_id': list_id,
        'item_list_name': list_name,
        'items': params.get('items', []),
    }
    return _datalayer_push('view_item_list', ecommerce)


@register.simple_tag
def dl_purchase(order):
    """`purchase` push for the order confirmation page. The
    transaction_id ensures GA dedups against the server-side hit."""
    if not order:
        return ''
    from plugins.installed.tracking.services.event_mapping import purchase
    try:
        _, params = purchase(order)
    except Exception:  # noqa: BLE001
        return ''
    ecommerce = {
        'transaction_id': params.get('transaction_id', ''),
        'currency': params.get('currency', 'USD'),
        'value': params.get('value', 0),
        'tax': params.get('tax', 0),
        'shipping': params.get('shipping', 0),
        'coupon': params.get('coupon', ''),
        'items': params.get('items', []),
    }
    return _datalayer_push('purchase', ecommerce)


@register.simple_tag
def tracking_consent_banner():
    """Tiny consent banner (off by default). When enabled the
    merchant gets a fixed-position banner with Accept / Reject buttons
    that update Consent Mode v2 signals via `gtag('consent','update',
    {...})`."""
    s = _settings()
    if s is None or not s.show_consent_banner:
        return ''
    return render_to_string('tracking/blocks/consent_banner.html', {'s': s})
