from __future__ import annotations

import json
import logging

from django.core.cache import cache
from django.core.cache.backends.base import CacheKeyWarning
from django.db import DatabaseError, connection
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

logger = logging.getLogger('morpheus.api.health')
csp_logger = logging.getLogger('morpheus.security.csp')


def healthz(request: HttpRequest) -> JsonResponse:
    """Liveness — process is up and able to respond."""
    return JsonResponse({'status': 'ok'})


@csrf_exempt
@require_http_methods(['POST'])
def csp_report(request: HttpRequest) -> HttpResponse:
    """Content-Security-Policy violation receiver.

    Receives the JSON envelope browsers POST when a page violates the
    CSP-Report-Only policy in core/security_headers.py. We log a
    structured event per report; if Sentry / OTel is wired in
    production, that's where these end up. Rate-limited at the LB
    layer; here we just trust the body and never let a single bad
    report break the page that triggered it.

    Browser sends either:
      Content-Type: application/csp-report  (legacy)
      Content-Type: application/reports+json (modern Reporting API)
    """
    try:
        body = request.body[:8192]  # cap report size; nothing legitimate is bigger
        if not body:
            return HttpResponse(status=204)
        report = json.loads(body)
    except (ValueError, TypeError, UnicodeDecodeError):
        return HttpResponse(status=204)  # malformed — silently drop

    # Both envelope shapes get normalised to a single log line.
    if isinstance(report, dict) and 'csp-report' in report:
        # Legacy CSP report-uri shape: { "csp-report": { ... } }
        r = report['csp-report'] or {}
        csp_logger.warning(
            'csp_violation directive=%s blocked=%s document=%s '
            'referrer=%s line=%s file=%s',
            r.get('violated-directive', '?'),
            r.get('blocked-uri', '?')[:200],
            r.get('document-uri', '?')[:200],
            r.get('referrer', '?')[:200],
            r.get('line-number', '?'),
            r.get('source-file', '?')[:200],
        )
    elif isinstance(report, list):
        # Reporting API shape: [{ "type": "csp-violation", "body": {...}}, …]
        for entry in report[:10]:
            if not isinstance(entry, dict):
                continue
            b = entry.get('body') or {}
            csp_logger.warning(
                'csp_violation directive=%s blocked=%s document=%s '
                'line=%s file=%s',
                b.get('effectiveDirective', '?'),
                b.get('blockedURL', '?')[:200],
                b.get('documentURL', '?')[:200],
                b.get('lineNumber', '?'),
                b.get('sourceFile', '?')[:200],
            )
    return HttpResponse(status=204)


def readyz(request: HttpRequest) -> JsonResponse:
    """Readiness — DB and cache are reachable."""
    checks = {'db': False, 'cache': False}

    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()
        checks['db'] = True
    except DatabaseError as e:
        logger.warning("readyz: db check failed: %s", e)

    try:
        cache.get('morpheus:readyz')
        checks['cache'] = True
    except (ConnectionError, OSError, CacheKeyWarning) as e:
        logger.warning("readyz: cache check failed: %s", e)
    except Exception as e:  # noqa: BLE001 — backend-specific errors logged, returns degraded
        logger.warning("readyz: cache check failed: %s", e)

    ok = all(checks.values())
    return JsonResponse(
        {'status': 'ok' if ok else 'degraded', 'checks': checks},
        status=200 if ok else 503,
    )


def healthz_deep(request: HttpRequest) -> JsonResponse:
    """Deep health — DB + cache + plugin registry + agent runtime + outbox lag."""
    checks: dict[str, dict] = {}

    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()
        checks['db'] = {'ok': True}
    except DatabaseError as e:
        checks['db'] = {'ok': False, 'error': str(e)[:200]}

    try:
        cache.set('morpheus:hzdeep', '1', timeout=10)
        checks['cache'] = {'ok': cache.get('morpheus:hzdeep') == '1'}
    except Exception as e:  # noqa: BLE001
        checks['cache'] = {'ok': False, 'error': str(e)[:200]}

    try:
        from plugins.registry import plugin_registry
        active = list(plugin_registry._active)
        checks['plugins'] = {'ok': True, 'active_count': len(active)}
    except Exception as e:  # noqa: BLE001
        checks['plugins'] = {'ok': False, 'error': str(e)[:200]}

    try:
        from core.agents import agent_registry
        checks['agents'] = {
            'ok': True,
            'agents': len(agent_registry.all_agents()),
            'tools': len(agent_registry.platform_tools()),
        }
    except Exception as e:  # noqa: BLE001
        checks['agents'] = {'ok': False, 'error': str(e)[:200]}

    try:
        from core.assistant.providers import get_default_provider
        provider = get_default_provider()
        checks['assistant'] = {'ok': True, 'provider': provider.name, 'model': provider.model}
    except Exception as e:  # noqa: BLE001
        checks['assistant'] = {'ok': False, 'error': str(e)[:200]}

    try:
        from core.models import OutboxEvent
        unsent = OutboxEvent.objects.filter(sent_at__isnull=True).count()
        checks['outbox'] = {'ok': unsent < 1000, 'unsent': unsent}
    except Exception as e:  # noqa: BLE001
        checks['outbox'] = {'ok': True, 'note': 'unavailable'}

    ok = all(c.get('ok', False) for c in checks.values())
    return JsonResponse(
        {'status': 'ok' if ok else 'degraded', 'checks': checks},
        status=200 if ok else 503,
    )
