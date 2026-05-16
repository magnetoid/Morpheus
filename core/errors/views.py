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

    total_server = ErrorEvent.objects.filter(kind='server').count()
    total_client = ErrorEvent.objects.filter(kind='client').count()

    return render(request, 'admin_dashboard/errors_list.html', {
        'rows': list(grouped),
        'kind_filter': kind,
        'search': search,
        'total_server': total_server,
        'total_client': total_client,
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
