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
        from plugins.registry import plugin_registry

        rows = []
        for p in sorted(plugin_registry.all_plugins(), key=lambda x: x.name):
            rows.append(
                {
                    'name': p.name,
                    'label': getattr(p, 'label', p.name),
                    'version': getattr(p, 'version', ''),
                    'active': plugin_registry.is_active(p.name),
                    'has_models': getattr(p, 'has_models', False),
                    'requires': list(getattr(p, 'requires', []) or []),
                }
            )
        errors: list = []
        with suppress(Exception):
            errors = plugin_registry.validate() or []
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
    with suppress(Exception):
        from core.assistant.models import CodeProposal

        out['proposals'] = [
            {
                'name': p.name,
                'status': p.status,
                'passed': p.passed,
                'findings': len(p.findings or []),
            }
            for p in CodeProposal.objects.filter(status='draft').order_by('-created_at')[:10]
        ]
    return out


def content_seo() -> dict:
    out: dict = {'available': True}
    with suppress(Exception):
        from django.db.models import Avg

        from plugins.installed.seo.models import SeoAuditResult

        low = SeoAuditResult.objects.order_by('score')[:20]
        out['low_seo'] = [{'score': a.score, 'issues': (a.issues or [])[:4]} for a in low]
        out['seo_avg'] = round(SeoAuditResult.objects.aggregate(a=Avg('score'))['a'] or 0, 1)
        out['seo_low_count'] = SeoAuditResult.objects.filter(score__lt=50).count()
        out['seo_total'] = SeoAuditResult.objects.count()
    with suppress(Exception):
        from plugins.installed.seo.models import NotFoundLog

        out['notfound'] = [
            {'path': n.path, 'hits': n.hit_count}
            for n in NotFoundLog.objects.order_by('-hit_count')[:10]
        ]
    with suppress(Exception):
        from django.db.models import Q

        from plugins.installed.catalog.models import Product

        active = Product.objects.filter(status='active')
        out['catalog'] = {
            'total': active.count(),
            'missing_desc': active.filter(Q(description__isnull=True) | Q(description='')).count(),
        }
    return out


def storefront() -> dict:
    out: dict = {'available': True}
    with suppress(Exception):
        from plugins.installed.seo.views import _cwv_summary

        out['cwv'] = _cwv_summary()
    with suppress(Exception):
        from plugins.installed.seo.services import site_settings

        s = site_settings()
        out['seo_flags'] = {
            'Organization JSON-LD': getattr(s, 'jsonld_organization', None),
            'Product JSON-LD': getattr(s, 'jsonld_product', None),
            'WebSite + search box': getattr(s, 'jsonld_website', None),
            'llms.txt': getattr(s, 'llms_txt_enabled', None),
            'AI answer block': getattr(s, 'ai_answer_block_enabled', None),
        }
    return out


def insights() -> dict:
    out: dict = {'available': True, 'insights': [], 'setup': []}
    with suppress(Exception):
        from plugins.installed.ai_assistant.models import MerchantInsight

        out['insights'] = [
            {
                'title': i.title,
                'type': getattr(i, 'insight_type', ''),
                'priority': getattr(i, 'priority', ''),
                'impact': getattr(i, 'estimated_impact', ''),
            }
            for i in MerchantInsight.objects.filter(is_read=False).order_by('-created_at')[:10]
        ]
    with suppress(Exception):
        from core.hooks import MorpheusEvents, hook_registry

        steps = hook_registry.filter(MorpheusEvents.DASHBOARD_SETUP_STEPS, value=[]) or []
        out['setup'] = [s for s in steps if isinstance(s, dict)]
    return out


def daily_reports() -> dict:
    """Daily curated AI reports covering Code Optimization, Feature Enhancements, and E-commerce Advancements."""
    out: dict = {'available': True, 'reports': []}
    with suppress(Exception):
        from plugins.installed.morpheus_brain.models import DailyReport
        # Get the latest 10 reports, grouped by category
        reports = DailyReport.objects.filter(is_published=True).order_by('-published_at')[:10]
        out['reports'] = [
            {
                'id': str(r.id),
                'title': r.title,
                'category': r.get_category_display(),
                'summary': r.summary,
                'content': r.content,
                'published_at': r.published_at,
                'references': [
                    {'title': ref.title, 'url': ref.url}
                    for ref in r.references.all()
                ]
            }
            for r in reports
        ]
    return out

def _gather_all_uncached() -> dict[str, Any]:
    """Everything the Brain knows, in one (DB-heavy) pass."""
    return {
        'plugins': plugins_health(),
        'errors': errors_signal(),
        'code': code_signal(),
        'content': content_seo(),
        'storefront': storefront(),
        'improvements': insights(),
        'reports': daily_reports(),
    }


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
