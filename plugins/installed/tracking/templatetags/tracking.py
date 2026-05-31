# ruff: noqa: PLC0415, S110, S308
# - PLC0415: inline imports avoid pulling the plugin registry + model
#   modules at templatetag-load time (Django loads templatetags very
#   early). Each tag pays only for what it actually uses.
# - S110: defensive try/except/pass around settings lookup is deliberate
#   — a missing TrackingSettings row must never break a storefront page.
# - S308: mark_safe is applied only to JSON-encoded payloads we built
#   ourselves from validated TrackingSettings — never to raw user input.
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

from plugins.installed.consent.services import read_consent_from_cookie
from plugins.installed.tracking.models import TrackingSettings

register = template.Library()


def _settings():
    try:
        return TrackingSettings.get_solo()
    except Exception:  # noqa: BLE001 — table missing pre-migration
        return None


def _has_consent(request, category: str) -> bool:
    """True if the visitor has opted in to ``category`` (analytics /
    marketing / functional). Missing request or missing cookie → False:
    we silently no-op until the banner is answered.

    Compliance escape hatch: when TrackingSettings.consent_override is
    True, this returns True unconditionally. Intended for staging,
    internal staff visits, and non-EU shops only.
    """
    try:
        s = _settings()
        if s is not None and getattr(s, 'consent_override', False):
            return True
    except Exception:  # noqa: BLE001
        pass
    if request is None:
        return False
    try:
        return bool(read_consent_from_cookie(request).get(category))
    except Exception:  # noqa: BLE001
        return False


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


@register.simple_tag(takes_context=True)
def gtm_head(context):
    """Emit the GTM head snippet. No-op when GTM container is not
    configured OR client-side firing is off OR the visitor has not
    granted analytics consent (GDPR / ePrivacy)."""
    s = _settings()
    if s is None or not s.client_side_enabled or not s.gtm_container_id:
        return ''
    if not _has_consent(context.get('request'), 'analytics'):
        return ''
    gtm = s.gtm_container_id
    return mark_safe(
        '<script>'
        "(function(w,d,s,l,i){w[l]=w[l]||[];w[l].push({'gtm.start':"
        "new Date().getTime(),event:'gtm.js'});var f=d.getElementsByTagName(s)[0],"
        "j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;"
        "j.src='https://www.googletagmanager.com/gtm.js?id='+i+dl;"
        'f.parentNode.insertBefore(j,f);'
        f"}})(window,document,'script','dataLayer','{gtm}');"
        '</script>'
    )


@register.simple_tag(takes_context=True)
def gtm_noscript_body(context):
    """Emit the immediate-after-`<body>` noscript fallback iframe.
    Gated on analytics consent — without opt-in the iframe never loads."""
    s = _settings()
    if s is None or not s.client_side_enabled or not s.gtm_container_id:
        return ''
    if not _has_consent(context.get('request'), 'analytics'):
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


def _ads_config():
    """Read Google Ads conversion knobs from the tracking plugin's
    PluginConfig (kept in JSON to avoid a TrackingSettings model migration).
    """
    try:
        from plugins.registry import plugin_registry

        p = plugin_registry.get('tracking')
        if p is None:
            return '', ''
        cfg = p.get_config() or {}
        return (
            (cfg.get('google_ads_conversion_id') or '').strip(),
            (cfg.get('google_ads_purchase_label') or '').strip(),
        )
    except Exception:  # noqa: BLE001
        return '', ''


@register.simple_tag
def gads_purchase_conversion(order):
    """Emit a Google Ads `conversion` event for the order. Only fires
    when both google_ads_conversion_id (AW-XXXXXXXXX) AND
    google_ads_purchase_label are configured on the tracking plugin.

    Loads gtag.js inline if not already on the page (Consent Mode v2
    defaults emitted via {% gtm_consent_default %} still apply because
    they set on the shared dataLayer before any container boot).

    Usage on order_confirmation.html:

        {% load tracking %}
        {% gads_purchase_conversion order %}
    """
    if not order:
        return ''
    conv_id, label = _ads_config()
    if not conv_id or not label:
        return ''

    s = _settings()
    if s is not None and not s.client_side_enabled:
        return ''

    # Derive value/currency from the order. Reuse the same event_mapping
    # surface as GA4 so AOV / value semantics stay aligned across the
    # two networks.
    try:
        from plugins.installed.tracking.services.event_mapping import purchase

        _, params = purchase(order)
    except Exception:  # noqa: BLE001
        params = {}

    value = params.get('value', 0)
    currency = params.get('currency', 'USD')
    transaction_id = params.get('transaction_id', getattr(order, 'order_number', '')) or ''

    payload = {
        'send_to': f'{conv_id}/{label}',
        'value': value,
        'currency': currency,
        'transaction_id': transaction_id,
    }
    return mark_safe(
        '<script async '
        f'src="https://www.googletagmanager.com/gtag/js?id={conv_id}"></script>'
        '<script>'
        'window.dataLayer=window.dataLayer||[];'
        'function gtag(){dataLayer.push(arguments);}'
        f'gtag("js", new Date()); gtag("config", "{conv_id}");'
        f'gtag("event","conversion",{json.dumps(payload)});'
        '</script>'
    )


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
