"""HTTP endpoints: client error ingest + dashboard list/detail."""

from __future__ import annotations

import json
import logging

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.cache import cache
from django.db.models import Count, OuterRef, Subquery
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from core.authz import require_capability
from core.errors.models import ErrorEvent, ErrorGroup
from core.errors.services import _ip_hash, record_client_error

logger = logging.getLogger('morpheus.errors')


_MAX_BODY = 64 * 1024  # 64 KB — generous for a stack trace.

# Per-IP write rate limit on /api/errors/client/. The browser already has a
# 25-event cap + 5s dedup; the server cap defends against an attacker
# ignoring the JS and POSTing in a tight loop to fill the table.
_RL_MAX = 50  # requests
_RL_WINDOW = 60  # seconds


def _rate_limited(request) -> bool:
    """Return True if this IP has exhausted its quota in the current window."""
    bucket = _ip_hash(request) or 'anon'
    key = f'errs:client:{bucket}'
    # cache.incr requires the key to exist; add with timeout if missing.
    if not cache.add(key, 1, timeout=_RL_WINDOW):
        try:
            count = cache.incr(key)
        except ValueError:
            # Race: the key expired between add() and incr(). Re-add.
            cache.add(key, 1, timeout=_RL_WINDOW)
            return False
        return count > _RL_MAX
    return False


@csrf_exempt
@require_POST
def client_error_ingest(request: HttpRequest) -> HttpResponse:  # noqa: PLR0911
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

    if _rate_limited(request):
        return JsonResponse({'error': 'rate limit exceeded'}, status=429)

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
    return host in allowed or any(
        host.endswith('.' + a) for a in allowed if a and not a.startswith('.')
    )


# ── Dashboard views ──────────────────────────────────────────────────────────


@staff_member_required
def errors_list(request: HttpRequest) -> HttpResponse:
    """Grouped list of recent errors — one row per fingerprint."""
    from datetime import timedelta

    from django.db.models.functions import TruncHour
    from django.utils import timezone

    from core.errors.mode import WINDOWS, state
    from core.errors.report import status_of

    qs = ErrorEvent.objects.all()

    status_filter = request.GET.get('status', 'open')
    if status_filter not in ('open', 'resolved', 'all'):
        status_filter = 'open'
    kind = request.GET.get('kind', '')
    if kind in ('server', 'client'):
        qs = qs.filter(kind=kind)
    search = (request.GET.get('q') or '').strip()
    if search:
        qs = qs.filter(message__icontains=search) | qs.filter(exception_class__icontains=search)

    # Group by fingerprint. Use a correlated subquery for last_message /
    # last_path so they come from the row with the latest created_at — Max()
    # on text columns returns the lexically-greatest string, not the latest
    # row's value (would silently lie when messages differ across occurrences).
    latest = ErrorEvent.objects.filter(fingerprint=OuterRef('fingerprint')).order_by('-created_at')
    grouped = (
        qs.values('fingerprint', 'kind', 'level', 'exception_class')
        .annotate(
            seen=Count('id'),
            last_seen=Subquery(latest.values('created_at')[:1]),
            last_message=Subquery(latest.values('message')[:1]),
            last_path=Subquery(latest.values('path')[:1]),
        )
        .order_by('-last_seen')[:200]
    )
    rows = list(grouped)
    decisions = {
        g.fingerprint: g
        for g in ErrorGroup.objects.filter(fingerprint__in=[r['fingerprint'] for r in rows])
    }
    for r in rows:
        r['status'] = status_of(decisions.get(r['fingerprint']), r['last_seen'])
    if status_filter == 'open':
        rows = [r for r in rows if r['status'] != 'resolved']
    elif status_filter == 'resolved':
        rows = [r for r in rows if r['status'] == 'resolved']

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
        .values('hour')
        .annotate(c=Count('id'))
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

    return render(
        request,
        'admin_dashboard/errors_list.html',
        {
            'rows': rows,
            'kind_filter': kind,
            'status_filter': status_filter,
            'capture': state(),
            'capture_windows': WINDOWS,
            'search': search,
            'counts': counts,
            'spark_bars': spark_bars,
            'spark_max': spark_max,
            # Legacy keys (still used by the template for back-compat):
            'total_server': counts['server'],
            'total_client': counts['client'],
            'active_nav': 'errors',
        },
    )


@staff_member_required
def errors_detail(request: HttpRequest, fingerprint: str) -> HttpResponse:
    """Drill-in: all occurrences of one fingerprint."""
    qs = ErrorEvent.objects.filter(fingerprint=fingerprint).order_by('-created_at')[:50]
    rows = list(qs)
    if not rows:
        raise Http404('Unknown fingerprint')
    from core.errors.report import status_of

    decision = ErrorGroup.objects.filter(fingerprint=fingerprint).first()
    return render(
        request,
        'admin_dashboard/errors_detail.html',
        {
            'rows': rows,
            'head': rows[0],
            'count': ErrorEvent.objects.filter(fingerprint=fingerprint).count(),
            'status': status_of(decision, rows[0].created_at),
            'decision': decision,
            'fingerprint': fingerprint,
            'context': (rows[0].metadata or {}).get('context') or {},
            'active_nav': 'errors',
        },
    )


@staff_member_required
def errors_report(request: HttpRequest) -> HttpResponse:
    """The report for Claude Code: Markdown by default, JSON with ?format=json."""
    from django.utils import timezone

    from core.errors.report import build_report, render_markdown

    try:
        days = int(request.GET.get('days') or 7)
    except ValueError:
        days = 7
    fingerprint = (request.GET.get('fingerprint') or '').strip()[:64]
    report = build_report(
        days=days, include_resolved=request.GET.get('resolved') == '1', fingerprint=fingerprint
    )
    as_json = request.GET.get('format') == 'json'
    if as_json:
        response = JsonResponse(report)
    else:
        response = HttpResponse(
            render_markdown(report), content_type='text/markdown; charset=utf-8'
        )
    if request.GET.get('download') == '1':
        stamp = timezone.now().strftime('%Y%m%d-%H%M')
        response['Content-Disposition'] = (
            f'attachment; filename="errors-{stamp}.{"json" if as_json else "md"}"'
        )
    return response


@staff_member_required
@require_capability('system.write')
@require_POST
def errors_detailed(request: HttpRequest) -> HttpResponse:
    """Turn detailed capture on for a window, or off."""
    from core.errors.mode import WINDOWS, turn_off, turn_on

    if request.POST.get('action') == 'off':
        turn_off(user=request.user)
        messages.success(request, 'Detailed capture is off. Standard capture continues.')
    else:
        try:
            hours = int(request.POST.get('hours') or WINDOWS[0])
        except ValueError:
            hours = WINDOWS[0]
        if hours not in WINDOWS:
            hours = WINDOWS[0]
        until = turn_on(hours, user=request.user)
        messages.success(
            request, f'Detailed capture is on until {until:%b %d, %H:%M} UTC, then it switches off.'
        )
    return redirect('errors:list')


@staff_member_required
@require_capability('system.write')
@require_POST
def errors_resolve(request: HttpRequest, fingerprint: str) -> HttpResponse:
    """Mark a group resolved, or open it again."""
    from core.errors.report import reopen, resolve

    if request.POST.get('action') == 'reopen':
        reopen(fingerprint)
        messages.success(request, 'Opened again.')
    elif resolve(fingerprint, user=request.user, note=request.POST.get('note', '')):
        messages.success(request, 'Marked resolved. It opens again if the error comes back.')
    else:
        raise Http404('Unknown fingerprint')
    return redirect('errors:detail', fingerprint=fingerprint)
