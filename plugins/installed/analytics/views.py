"""Analytics HTTP surface: track beacon + dashboard pages."""

from __future__ import annotations

import json
import logging

from django.http import HttpResponse

from morpheus.views import (
    HttpResponseBadRequest,
    JsonResponse,
    csrf_exempt,
    render,
    require_http_methods,
    staff_member_required,
)

logger = logging.getLogger('morpheus.analytics')


_ALLOWED_KINDS = {
    'pageview',
    'product_view',
    'search',
    'cart',
    'checkout',
    'purchase',
    'signup',
    'login',
    'custom',
}

# Hard caps on beacon shape — anyone can POST to this endpoint, so we
# refuse to ingest oversized garbage rather than let a single visitor
# fill the events table with 10MB blobs.
_MAX_BODY_BYTES = 4096
_MAX_PAYLOAD_KEYS = 20
_MAX_PAYLOAD_VALUE_LEN = 500


@csrf_exempt
@require_http_methods(['POST'])
def track_beacon(request):
    """Storefront JS calls this with `{name, kind?, url?, product_slug?, search_query?}`.

    Always returns 204 quickly. Recording is best-effort; never raises to caller.
    """
    if len(request.body or b'') > _MAX_BODY_BYTES:
        return HttpResponse(status=413)
    try:
        body = (
            json.loads(request.body or b'{}')
            if request.content_type == 'application/json'
            else dict(request.POST.items())
        )
    except json.JSONDecodeError:
        return HttpResponseBadRequest('Invalid JSON')
    name = (body.get('name') or '').strip()[:120]
    if not name:
        return HttpResponseBadRequest('Missing name')

    kind = (body.get('kind') or 'custom').strip()
    if kind not in _ALLOWED_KINDS:
        kind = 'custom'

    payload = {
        k: (v[:_MAX_PAYLOAD_VALUE_LEN] if isinstance(v, str) else v)
        for k, v in body.items()
        if k not in ('name', 'kind', 'url', 'product_slug', 'search_query')
    }
    if len(payload) > _MAX_PAYLOAD_KEYS:
        return HttpResponseBadRequest('Too many payload keys')

    try:
        from plugins.installed.analytics.services import (  # noqa: PLC0415
            get_or_create_session,
            record_event,
        )

        response = JsonResponse({'ok': True}, status=204)
        session = get_or_create_session(request, response=response)
        record_event(
            name=name,
            kind=kind,
            request=request,
            session=session,
            url=(body.get('url') or '')[:500],
            product_slug=(body.get('product_slug') or '')[:200],
            search_query=(body.get('search_query') or '')[:200],
            payload=payload,
        )
        return response
    except Exception as e:  # noqa: BLE001 — beacon must never error
        logger.warning('analytics: beacon failed: %s', e)
        return JsonResponse({'ok': False}, status=204)


# ─────────────────────────────────────────────────────────────────────────────
# Dashboard pages
# ─────────────────────────────────────────────────────────────────────────────


@staff_member_required
def overview(request):
    from plugins.installed.analytics.services import (  # noqa: PLC0415
        agent_activity,
        summary_for,
        top_products,
        top_searches,
    )

    days = int(request.GET.get('days', 7) or 7)
    return render(
        request,
        'analytics/overview.html',
        {
            'summary': summary_for(days=days),
            'top_products': top_products(days=days, limit=10),
            'top_searches': top_searches(days=days, limit=10),
            'agent_activity': agent_activity(days=days),
            'days': days,
            'active_nav': 'analytics',
        },
    )


@staff_member_required
def realtime(request):
    from plugins.installed.analytics.services import real_time  # noqa: PLC0415

    return render(
        request,
        'analytics/realtime.html',
        {
            'data': real_time(minutes=int(request.GET.get('minutes', 30) or 30)),
            'active_nav': 'analytics',
        },
    )


@staff_member_required
def funnel_view(request):
    """Default funnel: pageview → product.viewed → cart.add → order.placed."""
    from plugins.installed.analytics.services import funnel_for  # noqa: PLC0415

    raw = (request.GET.get('steps') or '').strip()
    if raw:
        steps = [s.strip() for s in raw.split(',') if s.strip()]
    else:
        steps = ['pageview', 'product.viewed', 'cart.add', 'order.placed']
    days = int(request.GET.get('days', 30) or 30)
    rows = funnel_for(steps=steps, days=days)
    # Compute conversion percentages relative to step 1.
    base = rows[0]['sessions'] if rows else 0
    for r in rows:
        r['pct'] = round((100.0 * r['sessions'] / base), 1) if base else 0.0
    return render(
        request,
        'analytics/funnel.html',
        {
            'rows': rows,
            'steps': steps,
            'days': days,
            'active_nav': 'analytics',
        },
    )


@staff_member_required
def realtime_json(request):
    """JSON feed for the realtime dashboard's auto-refresh."""
    from plugins.installed.analytics.services import real_time  # noqa: PLC0415

    data = real_time(minutes=int(request.GET.get('minutes', 5) or 5))
    # JSONField output already; but datetimes need stringifying:
    for r in data['recent']:
        r['created_at'] = r['created_at'].isoformat()
    return JsonResponse(data)
