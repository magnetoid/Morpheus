"""Tracking dashboard views.

* `overview` — single-page summary: connection state, last 24h send
  rate, top events, top errors, last 10 audit rows, and a deep-link
  into the full event log.
* `settings_page` — the comprehensive backend control center the
  merchant uses to configure every knob (Connection / Event firing /
  Consent / Identity / Filters / Tests). Tab navigation via
  ``?tab=…`` query param so each tab is bookmarkable.
* `event_log` — paginated audit table.
* `event_detail` — full payload + response body of one row.
* `test_purchase` / `test_event` — fire synthetic events so the
  merchant can verify the integration without placing a real order.
* `connection_check` — JSON probe that POSTs to the GA4 Debug endpoint
  and reports validation errors back to the merchant.
* `gtm_container_export` — downloads a pre-built GTM container JSON
  ready for import.
"""

# ruff: noqa: PLC0415, B007, PLR0912, PLR0915
# - PLC0415: inline imports inside views avoid loading subsystems
#   (measurement_protocol, event_mapping, registry) at URLconf import.
# - PLR0912 / PLR0915: settings_page is a tab-routed POST handler —
#   each tab's branch is its own logical save. Splitting it would
#   muddy the request flow without removing complexity.
# - B007: `ts` is bound for tuple-unpack readability; renaming to `_ts`
#   would make the values_list shape opaque.

from __future__ import annotations

import json
import logging
import os

from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from morpheus.plugin.views import staff_member_required
from plugins.installed.tracking.models import (
    DEFAULT_CONSENT_DEFAULT,
    DEFAULT_ENHANCED_OVERRIDES,
    DEFAULT_EVENT_FIRING,
    GA4EventLog,
    TrackingSettings,
)

logger = logging.getLogger('morpheus.tracking.views')


def _stats() -> dict:
    """Cheap summary for the overview page."""
    from datetime import timedelta

    cutoff = timezone.now() - timedelta(hours=24)
    qs = GA4EventLog.objects.filter(fired_at__gte=cutoff)
    total = qs.count()
    sent = qs.filter(status=GA4EventLog.STATUS_SENT).count()
    errored = qs.filter(status=GA4EventLog.STATUS_ERROR).count()
    deduped = qs.filter(status=GA4EventLog.STATUS_DEDUPED).count()
    success_rate = (sent / total * 100) if total else 0.0
    by_event: dict[str, int] = {}
    for name, ts in qs.order_by('-fired_at').values_list('event_name', 'fired_at')[:500]:
        by_event[name] = by_event.get(name, 0) + 1
    top_events = sorted(by_event.items(), key=lambda kv: kv[1], reverse=True)[:8]
    return {
        'total_24h': total,
        'sent_24h': sent,
        'errored_24h': errored,
        'deduped_24h': deduped,
        'success_rate': success_rate,
        'top_events': top_events,
    }


@staff_member_required
def overview(request):
    s = TrackingSettings.get_solo()
    stats = _stats()
    recent = list(GA4EventLog.objects.all().order_by('-fired_at')[:10])
    last_sent = (
        GA4EventLog.objects.filter(status=GA4EventLog.STATUS_SENT).order_by('-fired_at').first()
    )
    return render(
        request,
        'tracking/overview.html',
        {
            'active_nav': 'tracking',
            's': s,
            'stats': stats,
            'recent': recent,
            'last_sent_at': getattr(last_sent, 'fired_at', None),
            'configured': bool(s.measurement_id and s.api_secret),
        },
    )


@staff_member_required
def settings_page(request):
    """Comprehensive control center. Tab strip across the top; each
    tab is its own POST endpoint via the ``action`` hidden field so
    saving one tab never overwrites the others."""
    s = TrackingSettings.get_solo()
    tab = (request.GET.get('tab') or 'connection').strip()
    flash = ''

    if request.method == 'POST':
        action = (request.POST.get('action') or '').strip()

        if action == 'connection':
            s.measurement_id = (request.POST.get('measurement_id') or '').strip()[:32]
            new_secret = (request.POST.get('api_secret') or '').strip()
            if new_secret and new_secret != '__unchanged__':
                s.api_secret = new_secret[:120]
            s.gtm_container_id = (request.POST.get('gtm_container_id') or '').strip()[:32]
            s.sgtm_server_url = (request.POST.get('sgtm_server_url') or '').strip()[:500]
            s.region = (request.POST.get('region') or 'global').strip()
            s.save()
            flash = 'Connection saved.'
            tab = 'connection'

        elif action == 'events':
            s.server_side_enabled = request.POST.get('server_side_enabled') == 'on'
            s.client_side_enabled = request.POST.get('client_side_enabled') == 'on'
            s.debug_mode = request.POST.get('debug_mode') == 'on'
            new_event_firing = {}
            for name in DEFAULT_EVENT_FIRING:
                new_event_firing[name] = request.POST.get(f'event_{name}') == 'on'
            s.event_firing = new_event_firing
            new_overrides = {}
            for name in DEFAULT_ENHANCED_OVERRIDES:
                new_overrides[name] = request.POST.get(f'enhanced_{name}') == 'on'
            s.enhanced_overrides = new_overrides
            s.save()
            flash = 'Event firing saved.'
            tab = 'events'

        elif action == 'consent':
            new_consent = {}
            for signal in DEFAULT_CONSENT_DEFAULT:
                val = (request.POST.get(f'consent_{signal}') or 'denied').strip()
                new_consent[signal] = 'granted' if val == 'granted' else 'denied'
            s.consent_default = new_consent
            s.consent_override = request.POST.get('consent_override') == 'on'
            s.show_consent_banner = request.POST.get('show_consent_banner') == 'on'
            s.banner_accept_label = (request.POST.get('banner_accept_label') or 'Accept all')[:40]
            s.banner_reject_label = (request.POST.get('banner_reject_label') or 'Reject')[:40]
            s.banner_body = (request.POST.get('banner_body') or '')[:400]
            s.banner_link_url = (request.POST.get('banner_link_url') or '')[:400]
            s.banner_placement = (request.POST.get('banner_placement') or 'bottom').strip()
            s.save()
            flash = 'Consent saved.'
            tab = 'consent'

        elif action == 'identity':
            s.user_id_enabled = request.POST.get('user_id_enabled') == 'on'
            s.cross_domain = (request.POST.get('cross_domain') or '').strip()[:400]
            s.save()
            flash = 'Identity saved.'
            tab = 'identity'

        elif action == 'filters':
            paths = [
                p.strip() for p in (request.POST.get('block_paths') or '').split('\n') if p.strip()
            ]
            bots = [
                p.strip() for p in (request.POST.get('bot_patterns') or '').split('\n') if p.strip()
            ]
            s.block_paths = paths[:50]
            s.bot_patterns = bots[:50]
            s.dedup_strategy = (request.POST.get('dedup_strategy') or 'transaction_id').strip()
            try:
                s.dedup_window_minutes = max(1, int(request.POST.get('dedup_window_minutes') or 60))
            except (TypeError, ValueError):
                s.dedup_window_minutes = 60
            s.save()
            flash = 'Filters & dedup saved.'
            tab = 'filters'

        elif action == 'consent_preset':
            preset = request.POST.get('preset', 'eea_strict')
            if preset == 'eea_strict':
                s.consent_default = {k: 'denied' for k in DEFAULT_CONSENT_DEFAULT}
            elif preset == 'permissive':
                s.consent_default = {k: 'granted' for k in DEFAULT_CONSENT_DEFAULT}
            s.save()
            flash = 'Consent preset applied.'
            tab = 'consent'

        # Re-render same tab with a flash message.
        return redirect(f'/dashboard/tracking/settings/?tab={tab}&saved=1')

    if request.GET.get('saved'):
        flash = 'Saved.'

    event_rows = []
    for name, default in DEFAULT_EVENT_FIRING.items():
        last = GA4EventLog.objects.filter(event_name=name).order_by('-fired_at').first()
        enabled = (s.event_firing or {}).get(name, default)
        event_rows.append(
            {
                'name': name,
                'enabled': enabled,
                'last_fired_at': last.fired_at if last else None,
            }
        )
    enhanced_rows = [
        {'name': name, 'enabled': (s.enhanced_overrides or {}).get(name, default)}
        for name, default in DEFAULT_ENHANCED_OVERRIDES.items()
    ]
    consent_rows = [
        {'signal': name, 'value': (s.consent_default or {}).get(name, default)}
        for name, default in DEFAULT_CONSENT_DEFAULT.items()
    ]
    return render(
        request,
        'tracking/settings.html',
        {
            'active_nav': 'tracking',
            's': s,
            'tab': tab,
            'flash': flash,
            'event_rows': event_rows,
            'enhanced_rows': enhanced_rows,
            'consent_rows': consent_rows,
        },
    )


@staff_member_required
def event_log(request):
    qs = GA4EventLog.objects.all().order_by('-fired_at')
    name = (request.GET.get('event') or '').strip()
    status = (request.GET.get('status') or '').strip()
    if name:
        qs = qs.filter(event_name=name)
    if status:
        qs = qs.filter(status=status)
    rows = list(qs[:200])
    return render(
        request,
        'tracking/event_log.html',
        {
            'active_nav': 'tracking',
            'rows': rows,
            'filter_event': name,
            'filter_status': status,
        },
    )


@staff_member_required
def event_detail(request, event_id):
    row = get_object_or_404(GA4EventLog, pk=event_id)
    return render(
        request,
        'tracking/event_detail.html',
        {
            'active_nav': 'tracking',
            'row': row,
            'payload_json': json.dumps(row.payload or {}, indent=2),
        },
    )


_TEST_EVENT_TEMPLATES = {
    'purchase': {
        'transaction_id': '__TXN__',
        'currency': 'USD',
        'value': 9.99,
        'items': [
            {'item_id': 'TEST-SKU', 'item_name': 'Test product', 'price': 9.99, 'quantity': 1}
        ],
    },
    'add_to_cart': {
        'currency': 'USD',
        'value': 9.99,
        'items': [
            {'item_id': 'TEST-SKU', 'item_name': 'Test product', 'price': 9.99, 'quantity': 1}
        ],
    },
    'view_item': {
        'currency': 'USD',
        'value': 9.99,
        'items': [
            {'item_id': 'TEST-SKU', 'item_name': 'Test product', 'price': 9.99, 'quantity': 1}
        ],
    },
    'begin_checkout': {
        'currency': 'USD',
        'value': 9.99,
        'items': [
            {'item_id': 'TEST-SKU', 'item_name': 'Test product', 'price': 9.99, 'quantity': 1}
        ],
    },
    'search': {'search_term': 'test query'},
    'sign_up': {'method': 'email'},
    'login': {'method': 'email'},
    'refund': {
        'transaction_id': '__TXN__',
        'currency': 'USD',
        'value': 9.99,
    },
    'remove_from_cart': {
        'currency': 'USD',
        'value': 9.99,
        'items': [
            {'item_id': 'TEST-SKU', 'item_name': 'Test product', 'price': 9.99, 'quantity': 1}
        ],
    },
}


@staff_member_required
def test_purchase(request):
    """Back-compat shim around test_event for the legacy 'send test
    purchase' button. Always fires the `purchase` template."""
    return test_event(request, event_name='purchase')


@staff_member_required
def test_event(request, event_name: str = 'purchase'):
    """Fire one synthetic GA4 event so the merchant can verify the
    integration end-to-end without placing a real order. Per-event
    payloads live in `_TEST_EVENT_TEMPLATES`."""
    from plugins.installed.tracking.services.measurement_protocol import send_event

    event_name = (event_name or 'purchase').strip()
    template = _TEST_EVENT_TEMPLATES.get(event_name)
    if template is None:
        return JsonResponse(
            {'ok': False, 'error': f'unknown event {event_name!r}'},
            status=400,
        )

    txn = f'TEST-{int(timezone.now().timestamp())}'
    # Shallow-copy + fill the transaction_id placeholder.
    params = {k: (txn if v == '__TXN__' else v) for k, v in template.items()}
    row = send_event(
        event_name=event_name,
        params=params,
        transaction_id=txn if 'transaction_id' in params else '',
    )
    if (request.GET.get('format') or '').lower() == 'json':
        return JsonResponse(
            {
                'ok': row.status == GA4EventLog.STATUS_SENT,
                'status': row.status,
                'event_log_id': row.pk,
                'event_log_url': f'/dashboard/tracking/events/{row.pk}/',
                'response_status': row.response_status,
                'error_message': row.error_message,
            }
        )
    return redirect(f'/dashboard/tracking/events/{row.pk}/')


@staff_member_required
def connection_check(request):  # noqa: ARG001 — staff-required GET
    """Probe the GA4 Measurement Protocol *debug* endpoint with the
    configured measurement_id + api_secret. Returns JSON describing
    whether the credentials are valid + any validation messages.

    Unlike `test_event`, this does NOT record an event in real reports —
    the `/debug/mp/collect` endpoint only validates payload + creds.
    """
    import json as _json  # noqa: PLC0415
    import urllib.error  # noqa: PLC0415
    import urllib.request  # noqa: PLC0415

    s = TrackingSettings.get_solo()
    if not s.measurement_id or not s.api_secret:
        return JsonResponse(
            {
                'ok': False,
                'reason': 'unconfigured',
                'message': 'Set measurement_id and api_secret first.',
            },
            status=400,
        )

    # Choose endpoint by region — same logic as send_event.
    if s.region == 'eu':
        base = 'https://www.google-analytics.com/debug/mp/collect'
    else:
        base = 'https://www.google-analytics.com/debug/mp/collect'
    url = f'{base}?measurement_id={s.measurement_id}&api_secret={s.api_secret}'

    body = _json.dumps(
        {
            'client_id': f'connection-check.{int(timezone.now().timestamp())}',
            'events': [{'name': 'page_view', 'params': {'page_title': 'connection_check'}}],
        }
    ).encode('utf-8')

    try:
        req = urllib.request.Request(  # noqa: S310 — hard-coded Google endpoint
            url,
            data=body,
            headers={
                'Content-Type': 'application/json; charset=utf-8',
                'User-Agent': 'Morpheus-Tracking/1.0',
            },
            method='POST',
        )
        with urllib.request.urlopen(req, timeout=6) as resp:  # noqa: S310  # nosec B310
            status_code = resp.status
            raw = (resp.read() or b'').decode('utf-8', errors='ignore')
    except urllib.error.HTTPError as exc:
        status_code = exc.code
        raw = (exc.read() or b'').decode('utf-8', errors='ignore') if hasattr(exc, 'read') else ''
    except Exception as exc:  # noqa: BLE001
        return JsonResponse(
            {'ok': False, 'reason': 'transport', 'message': str(exc)[:300]},
            status=502,
        )

    try:
        parsed = _json.loads(raw)
    except (ValueError, TypeError):
        parsed = {'raw': raw[:500]}

    validation = (parsed or {}).get('validationMessages') or []
    return JsonResponse(
        {
            'ok': status_code == 200 and not validation,
            'status_code': status_code,
            'validation_messages': validation,
            'endpoint': base,
            'measurement_id': s.measurement_id,
            'region': s.region,
            'debug_mode': s.debug_mode,
            'consent_override': getattr(s, 'consent_override', False),
        }
    )


@staff_member_required
def gtm_container_export(request):
    """Serve a pre-built GTM container JSON ready for the merchant to
    import into their workspace."""
    path = os.path.join(os.path.dirname(__file__), 'data', 'gtm_container.json')
    try:
        with open(path, encoding='utf-8') as f:
            body = f.read()
    except FileNotFoundError:
        body = json.dumps({'error': 'container template missing'})
    resp = HttpResponse(body, content_type='application/json; charset=utf-8')
    resp['Content-Disposition'] = 'attachment; filename="morpheus-ga4-container.json"'
    return resp
