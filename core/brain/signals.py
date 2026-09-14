"""Signal gathering for Morpheus Brain (core).

Read-only, fully defensive collectors over every analysis surface the platform
already produces: the self-improvement immune system (code-quality + error-log
signals, AI recommendations), plugin health, SEO/content audits, storefront
Core Web Vitals, and merchant insights. Each function swallows its own errors
and returns a partial/empty result so a missing engine never breaks the Brain.
"""

from __future__ import annotations

from contextlib import suppress
from typing import Any

from django.core.cache import cache

_SIGNALS_CACHE_KEY = 'brain:signals:v1'
_SIGNALS_TTL = 90  # seconds — the raw signals change slowly; the page GET is hot


def plugins_health() -> dict:
    try:
        from plugins.registry import app_registry

        rows = []
        for p in sorted(app_registry.all_plugins(), key=lambda x: x.name):
            rows.append(
                {
                    'name': p.name,
                    'label': getattr(p, 'label', p.name),
                    'version': getattr(p, 'version', ''),
                    'active': app_registry.is_active(p.name),
                    'has_models': getattr(p, 'has_models', False),
                    'requires': list(getattr(p, 'requires', []) or []),
                }
            )
        errors: list = []
        with suppress(Exception):
            errors = app_registry.validate() or []
        return {
            'available': True,
            'rows': rows,
            'total': len(rows),
            'active_count': sum(1 for r in rows if r['active']),
            'errors': errors,
        }
    except Exception:  # noqa: BLE001
        return {'available': False}


def _si_signals(source: str, limit: int = 15) -> list[dict]:
    """Recent self-improvement signals of one source (error_log, code_quality…)."""
    out: list[dict] = []
    with suppress(Exception):
        from core.self_improvement.models import SiSignal

        for s in SiSignal.objects.filter(source=source).order_by('-occurred_at')[:limit]:
            payload = s.payload if isinstance(s.payload, dict) else {}
            out.append(
                {
                    'severity': s.severity,
                    'seen_count': s.seen_count,
                    'summary': str(
                        payload.get('message')
                        or payload.get('title')
                        or payload.get('summary')
                        or s.fingerprint
                    )[:240],
                    'occurred_at': s.occurred_at,
                }
            )
    return out


def errors_signal() -> dict:
    """Recent error-log signals the immune system captured."""
    try:
        from core.self_improvement.models import SiSignal

        return {
            'available': True,
            'recent': _si_signals('error_log', 20),
            'total': SiSignal.objects.filter(source='error_log').count(),
        }
    except Exception:  # noqa: BLE001
        return {'available': False, 'recent': []}


def code_signal() -> dict:
    """Code-quality findings + AI recommendations + tracked drift."""
    out: dict = {'available': True}
    out['quality'] = _si_signals('code_quality', 20)
    with suppress(Exception):
        from core.self_improvement.models import SiSignal

        out['quality_total'] = SiSignal.objects.filter(source='code_quality').count()
    with suppress(Exception):
        from core.self_improvement.models import SiRecommendation

        recs = SiRecommendation.objects.filter(status='proposed').order_by('-impact_score')[:15]
        out['recommendations'] = [
            {
                'title': r.title,
                'class_name': r.class_name,
                'impact': r.impact_score,
                'rationale': (r.rationale or '')[:300],
            }
            for r in recs
        ]
        out['rec_total'] = SiRecommendation.objects.filter(status='proposed').count()
    with suppress(Exception):
        from core.self_improvement.models import SiCustomization

        out['drift_count'] = SiCustomization.objects.count()
    return out


def _setup_signal() -> dict:
    """Core-owned slice of the Improvements section: the first-run setup
    checklist (the DASHBOARD_SETUP_STEPS hook). The AI 'insights' half is
    contributed by ai_assistant through BRAIN_SIGNALS."""
    out: dict = {'available': True, 'insights': [], 'setup': []}
    with suppress(Exception):
        from core.hooks import MorpheusEvents, hook_registry

        steps = hook_registry.filter(MorpheusEvents.DASHBOARD_SETUP_STEPS, value=[]) or []
        out['setup'] = [s for s in steps if isinstance(s, dict)]
    return out


def _gather_all_uncached() -> dict[str, Any]:
    """Everything the Brain knows, in one (DB-heavy) pass.

    Core owns plugin health, the error-log + code-quality signals, and the
    setup checklist. Every *plugin-owned* slice — SEO/content audits, catalog
    gaps, Core Web Vitals, merchant insights, the daily AI reports — is merged
    in by its plugin through the BRAIN_SIGNALS filter, so the kernel imports no
    plugin model and a disabled contributor's Brain panel simply vanishes.
    """
    from core.hooks import MorpheusEvents, hook_registry

    data: dict[str, Any] = {
        'plugins': plugins_health(),
        'errors': errors_signal(),
        'code': code_signal(),
        'content': {'available': True},
        'storefront': {'available': True},
        'improvements': _setup_signal(),
        'reports': {'available': False},
    }
    return hook_registry.filter(MorpheusEvents.BRAIN_SIGNALS, value=data)


def gather_all() -> dict[str, Any]:
    """Cached signal snapshot — ~18 DB queries collapse to one cache hit on a hot
    page GET. Refreshed when the Refresh-analysis action calls
    invalidate_signals_cache(). Redis IGNORE_EXCEPTIONS=True → safe degrade to
    uncached on an outage."""
    data = cache.get(_SIGNALS_CACHE_KEY)
    if data is None:
        data = _gather_all_uncached()
        cache.set(_SIGNALS_CACHE_KEY, data, _SIGNALS_TTL)
    return data


def invalidate_signals_cache() -> None:
    cache.delete(_SIGNALS_CACHE_KEY)
