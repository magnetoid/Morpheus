# ruff: noqa: PLC0415, S110, S308
# - PLC0415: inline imports avoid pulling the plugin registry + model
#   modules at templatetag-load time (Django loads templatetags very
#   early). Each tag pays only for what it actually uses.
# - S110: defensive try/except/pass around settings lookup is deliberate
#   — a missing TrackingSettings row must never break a storefront page.
# - S308: mark_safe is applied only to JSON-encoded payloads we built
#   ourselves from validated TrackingSettings — never to raw user input.
"""Template tags for the storefront integration.

The page tags arrive through the app's own storefront blocks, so every theme
gets them from the slots it already emits and they leave with the app:

    global_head        → {% tracking_head %}      consent defaults, then GTM or GA4
    global_below_body  → {% tracking_noscript %}  GTM's no-JavaScript fallback

Plus per-event dataLayer push partials surfaced as `{% dl_view_item product %}`
etc. — these include a small template that prepends `dataLayer.push({ecommerce: null})`
to prevent items leaking between events (the #1 production bug per the
2026 research).
"""

from __future__ import annotations

import json
import re
from typing import Any

from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

from plugins.installed.tracking.models import TrackingSettings

register = template.Library()

_GOOGLE = 'https://www.googletagmanager.com'
_TAG_ID = re.compile(r'^(G|GTM|AW)-[A-Z0-9]{4,20}$')


def _settings():
    try:
        return TrackingSettings.get_solo()
    except Exception:  # noqa: BLE001 — table missing pre-migration
        return None


def _js(value) -> str:
    """JSON for inside a <script>: `<` escaped, so no stored text can close the tag."""
    return json.dumps(value).replace('<', '\\u003c')


def _tag_id(value) -> str:
    """A GA4 / GTM id fit to print into a script, else '' (the field is free text)."""
    value = (value or '').strip().upper()
    return value if _TAG_ID.match(value) else ''


def _visitor_allows(s, request) -> tuple[bool, bool]:
    """(analytics, marketing) for this visitor: the rule every sender reads
    (`core.consent`: a store that does not manage consent allows both), or both
    under the debug-only "Ignore visitor consent" switch."""
    if getattr(s, 'consent_override', False):
        return True, True
    from core.consent import decision_for

    decision = decision_for(request)
    managed = decision.get('managed')
    return (not managed or decision['analytics'], not managed or decision['marketing'])


def _linker_domains(s, request) -> list[str]:
    domains = [d.strip().lower() for d in (s.cross_domain or '').split(',') if d.strip()]
    if domains and request is not None:
        try:
            host = request.get_host().split(':')[0].lower()
        except Exception:  # noqa: BLE001 — DisallowedHost: the middleware has answered it
            host = ''
        if host and host not in domains:
            domains.insert(0, host)
    return domains


def _browser_user_id(s, request) -> str:
    if not s.user_id_enabled or request is None:
        return ''
    user = getattr(request, 'user', None)
    if not getattr(user, 'is_authenticated', False):
        return ''
    from plugins.installed.tracking.services.identity import user_id

    return user_id(user.pk)


def _tag_origin(s) -> str:
    """Where gtm.js / gtag.js load from: a server-side GTM container when set."""
    url = (s.sgtm_server_url or '').strip().rstrip('/')
    return url if url.startswith('https://') else _GOOGLE


def browser_tagging(s) -> bool:
    """Is a Google tag loaded in the shopper's browser (GTM, or GA4 itself)?"""
    return bool(
        s.client_side_enabled and (_tag_id(s.gtm_container_id) or _tag_id(s.measurement_id))
    )


@register.simple_tag(takes_context=True)
def tracking_head(context):
    """Consent Mode v2 defaults, the visitor's own decision, then GTM — or GA4's
    gtag.js when no container is set.

    The defaults print first and on every page (Google requires them before any
    tag, and the Ads tags read them too). A tag loads only when the visitor
    allows analytics; it then gets a consent update, so GA4 runs with the
    visitor's real choice rather than the denied defaults.
    """
    s = _settings()
    if s is None or not s.client_side_enabled:
        return ''
    request = context.get('request')
    js = [
        'window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments);}',
        f'gtag("consent","default",{_js(s.consent_default or {})});',
    ]
    gtm, ga4 = _tag_id(s.gtm_container_id), _tag_id(s.measurement_id)
    analytics, marketing = _visitor_allows(s, request)
    blocked = request is not None and s.is_path_blocked(request.path)
    if not (gtm or ga4) or not analytics or blocked:
        return mark_safe(f'<script>{"".join(js)}</script>')

    ads = 'granted' if marketing else 'denied'
    update = {
        'analytics_storage': 'granted',
        'ad_storage': ads,
        'ad_user_data': ads,
        'ad_personalization': ads,
    }
    js.append(f'gtag("consent","update",{_js(update)});')
    domains = _linker_domains(s, request)
    if domains:
        js.append(f'gtag("set","linker",{_js({"domains": domains})});')
    uid = _browser_user_id(s, request)
    origin = _tag_origin(s)
    if gtm:
        if uid:
            js.append(f'dataLayer.push({_js({"user_id": uid})});')
        js.append(
            "dataLayer.push({'gtm.start':new Date().getTime(),event:'gtm.js'});"
            '(function(d,s){var f=d.getElementsByTagName(s)[0],j=d.createElement(s);'
            f'j.async=true;j.src={_js(f"{origin}/gtm.js?id={gtm}")};'
            "f.parentNode.insertBefore(j,f);})(document,'script');"
        )
        return mark_safe(f'<script>{"".join(js)}</script>')
    config: dict[str, Any] = {}
    if uid:
        config['user_id'] = uid
    if origin != _GOOGLE:
        config['server_container_url'] = origin
    js.append(f'gtag("js",new Date());gtag("config",{_js(ga4)},{_js(config)});')
    src = escape(f'{origin}/gtag/js?id={ga4}')
    return mark_safe(f'<script>{"".join(js)}</script><script async src="{src}"></script>')


@register.simple_tag(takes_context=True)
def tracking_noscript(context):
    """GTM's fallback for browsers without JavaScript, under the same consent rule."""
    s = _settings()
    if s is None or not s.client_side_enabled:
        return ''
    gtm = _tag_id(s.gtm_container_id)
    request = context.get('request')
    if not gtm or not _visitor_allows(s, request)[0]:
        return ''
    if request is not None and s.is_path_blocked(request.path):
        return ''
    src = escape(f'{_tag_origin(s)}/ns.html?id={gtm}')
    return mark_safe(
        f'<noscript><iframe src="{src}" '
        'height="0" width="0" style="display:none;visibility:hidden"></iframe></noscript>'
    )


@register.simple_tag
def gtm_consent_default():
    """Retired in v0.127.0: `tracking_head` arrives through `global_head`. Renders
    nothing, so a theme outside this repo that still calls it neither breaks nor
    loads the tags twice — remove in the next MINOR."""
    return ''


@register.simple_tag
def gtm_head():
    """Retired in v0.127.0 with `gtm_consent_default` (see there)."""
    return ''


@register.simple_tag
def gtm_noscript_body():
    """Retired in v0.127.0: `tracking_noscript` arrives through `global_below_body`."""
    return ''


def _datalayer_push(event_name: str, ecommerce: dict[str, Any]) -> str:
    """One ecommerce event for the browser's tag.

    For GTM: a dataLayer.push() pair with the mandatory ecommerce-null reset.
    For GA4 without a container: a gtag event — gtag.js never reads a pushed
    `{event: …}` object, only GTM does.

    Sent once the page is parsed: themes print these in `extra_head`, which can
    come before `global_head`, and an event queued ahead of the Consent Mode
    defaults (or of gtag's config) would be processed before them.
    """
    s = _settings()
    if s is None or not s.client_side_enabled:
        return ''
    if not s.event_enabled(event_name):
        return ''
    if not _tag_id(s.gtm_container_id) and _tag_id(s.measurement_id):
        send = (
            'window.gtag=window.gtag||function(){dataLayer.push(arguments);};'
            f'gtag("event",{_js(event_name)},{_js(ecommerce)});'
        )
    else:
        body = _js({'event': event_name, 'ecommerce': ecommerce})
        send = f'dataLayer.push({{ecommerce:null}});dataLayer.push({body});'
    return mark_safe(
        '<script>window.dataLayer=window.dataLayer||[];(function(f){'
        "document.readyState==='loading'?document.addEventListener('DOMContentLoaded',f):f();"
        f'}})(function(){{{send}}});</script>'
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
        from plugins.registry import app_registry

        p = app_registry.get('tracking')
        if p is None:
            return '', ''
        cfg = p.get_config() or {}
        return (
            (cfg.get('google_ads_conversion_id') or '').strip(),
            (cfg.get('google_ads_purchase_label') or '').strip(),
        )
    except Exception:  # noqa: BLE001
        return '', ''


@register.simple_tag(takes_context=True)
def gads_purchase_conversion(context, order):
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
    # The consent app's decision (absent when the app is off: an unmanaged store).
    consent = context.get('consent') or {}
    if consent.get('managed') and not consent.get('marketing'):
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
    """Retired in v0.113.0 (the consent app is the one cookie banner); renders
    nothing. Kept for one release so a theme outside this repo that still calls
    it does not fail every storefront page — remove in the next MINOR."""
    return ''
