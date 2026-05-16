"""HTTP endpoints: client error ingest + dashboard list/detail."""
from __future__ import annotations

import json
import logging

from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Max
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from core.errors.models import ErrorEvent
from core.errors.services import record_client_error

logger = logging.getLogger('morpheus.errors')


_MAX_BODY = 64 * 1024  # 64 KB — generous for a stack trace.


@csrf_exempt
@require_POST
def client_error_ingest(request: HttpRequest) -> HttpResponse:
    """Receive JS errors from the browser.

    Payload (all optional except `message`)::

        {
          "message": "...",
          "name":    "TypeError",
          "source":  "https://.../app.js",
          "lineno":  42, "colno": 17,
          "stack":   "...",
          "page":    "https://.../path",
          "browser": "Chrome/148",
          "level":   "error"
        }

    Origin allow-list: the browser must share a host with our ALLOWED_HOSTS
    (i.e. requests from random external pages can't seed our log).
    """
    if int(request.META.get('CONTENT_LENGTH') or 0) > _MAX_BODY:
        return JsonResponse({'error': 'payload too large'}, status=413)

    origin = request.headers.get('Origin', '') or request.headers.get('Referer', '')
    if origin and not _origin_allowed(origin):
        return JsonResponse({'error': 'origin not allowed'}, status=403)

    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'error': 'bad json'}, status=400)

    if not isinstance(payload, dict) or not payload.get('message'):
        return JsonResponse({'error': 'message required'}, status=400)

    try:
        record_client_error(payload, request=request)
    except Exception:  # noqa: BLE001 — never break the page on our own bug
        logger.exception('client_error_ingest store failed')
        return JsonResponse({'error': 'store failed'}, status=500)
    return JsonResponse({'ok': True})


def _origin_allowed(origin: str) -> bool:
    from django.conf import settings
    try:
        from urllib.parse import urlparse
        host = (urlparse(origin).hostname or '').lower()
    except Exception:  # noqa: BLE001
        return False
    if not host:
        return False
    allowed = {h.lower() for h in (getattr(settings, 'ALLOWED_HOSTS', []) or [])}
    if '*' in allowed:
        return True
    return host in allowed or any(host.endswith('.' + a) for a in allowed if a and not a.startswith('.'))


# ── Dashboard views ──────────────────────────────────────────────────────────

@staff_member_required
def errors_list(request: HttpRequest) -> HttpResponse:
    """Grouped list of recent errors — one row per fingerprint."""
    from datetime import timedelta
    from django.db.models.functions import TruncHour
    from django.utils import timezone

    qs = ErrorEvent.objects.all()

    kind = request.GET.get('kind', '')
    if kind in ('server', 'client'):
        qs = qs.filter(kind=kind)
    search = (request.GET.get('q') or '').strip()
    if search:
        qs = qs.filter(message__icontains=search) | qs.filter(exception_class__icontains=search)

    grouped = (
        qs.values('fingerprint', 'kind', 'level', 'exception_class')
        .annotate(seen=Count('id'), last_seen=Max('created_at'),
                  last_message=Max('message'), last_path=Max('path'))
        .order_by('-last_seen')[:200]
    )

    # Summary counters across the same filter as the list — gives context
    # without forcing the user to add `?kind=...` to the URL.
    now = timezone.now()
    last_24h = now - timedelta(hours=24)
    last_7d = now - timedelta(days=7)
    counts = {
        'total': qs.count(),
        'last_24h': qs.filter(created_at__gte=last_24h).count(),
        'last_7d': qs.filter(created_at__gte=last_7d).count(),
        'server': ErrorEvent.objects.filter(kind='server').count(),
        'client': ErrorEvent.objects.filter(kind='client').count(),
    }

    # 24-bucket hourly sparkline. Build a {hour: count} dict, zero-fill,
    # then pre-compute SVG bar coords in Python so the template can stay
    # dumb (Django templates don't do arithmetic well).
    by_hour = {
        row['hour']: row['c']
        for row in qs.filter(created_at__gte=last_24h)
                     .annotate(hour=TruncHour('created_at'))
                     .values('hour').annotate(c=Count('id'))
    }
    raw = []
    for i in range(24, 0, -1):
        bucket = (now - timedelta(hours=i)).replace(minute=0, second=0, microsecond=0)
        raw.append(by_hour.get(bucket, 0))
    spark_max = max(raw) or 1
    # Each bar: x in [0..480], y from bottom (56), width 18, evenly spaced.
    spark_bars = []
    for idx, v in enumerate(raw):
        x = int(idx * 480 / 24)
        h = int(v * 56 / spark_max) if v else 1
        y = 56 - h
        spark_bars.append({'x': x, 'y': y, 'h': h, 'v': v})

    return render(request, 'admin_dashboard/errors_list.html', {
        'rows': list(grouped),
        'kind_filter': kind,
        'search': search,
        'counts': counts,
        'spark_bars': spark_bars,
        'spark_max': spark_max,
        # Legacy keys (still used by the template for back-compat):
        'total_server': counts['server'],
        'total_client': counts['client'],
        'active_nav': 'errors',
    })


@staff_member_required
def errors_detail(request: HttpRequest, fingerprint: str) -> HttpResponse:
    """Drill-in: all occurrences of one fingerprint."""
    qs = ErrorEvent.objects.filter(fingerprint=fingerprint).order_by('-created_at')[:50]
    rows = list(qs)
    if not rows:
        from django.http import Http404
        raise Http404('Unknown fingerprint')
    return render(request, 'admin_dashboard/errors_detail.html', {
        'rows': rows,
        'head': rows[0],
        'count': qs.count() if hasattr(qs, 'count') else len(rows),
        'active_nav': 'errors',
    })
