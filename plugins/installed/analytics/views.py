"""Analytics HTTP surface: track beacon + dashboard pages."""

from __future__ import annotations

import contextlib
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
    'click',
    'form_submit',
    'scroll',
    'error',
}

# Hard caps on beacon shape — anyone can POST to this endpoint, so we
# refuse to ingest oversized garbage rather than let a single visitor
# fill the events table with 10MB blobs.
_MAX_BODY_BYTES = 8192
_MAX_PAYLOAD_KEYS = 30
_MAX_PAYLOAD_VALUE_LEN = 1000


@csrf_exempt
def custom_events_config(request):
    """Returns the list of active CustomEventConfig items for the frontend JS to attach listeners."""
    from plugins.installed.analytics.models import CustomEventConfig

    try:
        events = list(
            CustomEventConfig.objects.filter(is_active=True).values(
                'name', 'css_selector', 'url_pattern', 'event_kind'
            )
        )
        return JsonResponse({'events': events})
    except Exception:
        return JsonResponse({'events': []})


@csrf_exempt
@require_http_methods(['POST'])
def track_beacon(request):
    """Storefront JS calls this with `{name, kind?, url?, product_slug?, search_query?, scroll_depth?, duration_ms?, error_context?}`.

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
        if k
        not in (
            'name',
            'kind',
            'url',
            'product_slug',
            'search_query',
            'scroll_depth',
            'duration_ms',
            'error_context',
            'is_realtime',
        )
    }
    if len(payload) > _MAX_PAYLOAD_KEYS:
        return HttpResponseBadRequest('Too many payload keys')

    try:
        from plugins.installed.analytics.services import (  # noqa: PLC0415
            get_or_create_session,
            record_event,
            should_track_request,
        )

        response = JsonResponse({'ok': True}, status=204)
        # Skip staff/admin browsing so it doesn't pollute customer analytics.
        if should_track_request(request):
            session = get_or_create_session(request, response=response)

            # Extract new metrics
            scroll_depth = None
            if body.get('scroll_depth') is not None:
                with contextlib.suppress(ValueError):
                    scroll_depth = int(body.get('scroll_depth'))

            duration_ms = None
            if body.get('duration_ms') is not None:
                with contextlib.suppress(ValueError):
                    duration_ms = int(body.get('duration_ms'))

            error_context = body.get('error_context') or {}
            if isinstance(error_context, str):
                try:
                    error_context = json.loads(error_context)
                except json.JSONDecodeError:
                    error_context = {'raw': error_context}

            is_realtime = bool(body.get('is_realtime', False))

            record_event(
                name=name,
                kind=kind,
                request=request,
                session=session,
                url=(body.get('url') or '')[:500],
                product_slug=(body.get('product_slug') or '')[:200],
                search_query=(body.get('search_query') or '')[:200],
                payload=payload,
                scroll_depth=scroll_depth,
                duration_ms=duration_ms,
                error_context=error_context,
                is_realtime=is_realtime,
            )
        return response
    except Exception as e:  # noqa: BLE001 — beacon must never error
        logger.warning('analytics: beacon failed: %s', e)
        return JsonResponse({'ok': False}, status=204)


@staff_member_required
def export_data(request):
    """Export analytics data in CSV/JSON format."""
    import csv

    from plugins.installed.analytics.services import (
        summary_for,
        top_products,
    )

    format_type = request.GET.get('format', 'csv')
    days = int(request.GET.get('days', 30))

    summary = summary_for(days=days)
    products = top_products(days=days, limit=100)

    if format_type == 'json':
        response = JsonResponse({'summary': summary, 'top_products': products})
        response['Content-Disposition'] = f'attachment; filename="analytics_export_{days}d.json"'
        return response

    # CSV Default
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="analytics_export_{days}d.csv"'

    writer = csv.writer(response)
    writer.writerow(['Metric', 'Value'])
    for key, value in summary.items():
        writer.writerow([key, str(value)])

    writer.writerow([])
    writer.writerow(['Top Products'])
    writer.writerow(['Product Slug', 'Views'])
    for p in products:
        writer.writerow([p['product_slug'], p['views']])

    return response


@staff_member_required
def overview(request):
    from plugins.installed.analytics.services import (  # noqa: PLC0415
        agent_activity,
        predictive_trends,
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
            'forecast': predictive_trends(days=days),
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
    """Default funnel: pageview → product.viewed → cart.add → checkout.started → order.placed.

    Augmented (sprint #4): per-step drop-off detail + period comparison
    so engineers can see *which* transition is the worst and whether
    the overall funnel is improving over time, not just the snapshot.
    """
    from plugins.installed.analytics.services import funnel_for  # noqa: PLC0415
    from plugins.installed.analytics.services_cohorts import (  # noqa: PLC0415
        period_comparison,
        step_dropoffs,
    )

    raw = (request.GET.get('steps') or '').strip()
    if raw:
        steps = [s.strip() for s in raw.split(',') if s.strip()]
    else:
        steps = ['pageview', 'product.viewed', 'cart.add', 'checkout.started', 'order.placed']
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
            'dropoffs': step_dropoffs(steps=steps, days=days),
            'comparison': period_comparison(days=days),
            'active_nav': 'analytics',
        },
    )


@staff_member_required
def cohort_view(request):
    """Weekly cohort retention table — % of customers signing up in
    week W who placed an order in week W+N, for N = 0..11.

    The single most important metric besides revenue: tells you
    whether each marketing dollar is buying recurring revenue or
    just one-time transactions.
    """
    from plugins.installed.analytics.services_cohorts import compute_cohorts  # noqa: PLC0415

    metric = (request.GET.get('metric') or 'order').strip()
    if metric not in ('order', 'active', 'revenue'):
        metric = 'order'
    cohort_count = max(1, min(26, int(request.GET.get('cohorts', 8) or 8)))
    period_count = max(1, min(26, int(request.GET.get('periods', 12) or 12)))
    return render(
        request,
        'analytics/cohorts.html',
        {
            'cohort_data': compute_cohorts(
                cohort_count=cohort_count,
                period_count=period_count,
                metric=metric,
            ),
            'metric': metric,
            'cohort_count': cohort_count,
            'period_count': period_count,
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
