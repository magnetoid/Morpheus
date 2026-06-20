"""Morpheus Brain view — defensive aggregation of platform signals.

Every helper is wrapped: a missing model, disabled plugin, or schema drift
yields ``{'available': False}`` for that section instead of 500-ing the page.
The whole console is read-only.
"""

from __future__ import annotations

from contextlib import suppress

from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render


def _plugins_tab() -> dict:
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
        errors = []
        with suppress(Exception):
            errors = plugin_registry.validate() or []
        return {
            'available': True,
            'rows': rows,
            'total': len(rows),
            'active_count': sum(1 for r in rows if r['active']),
            'disabled': [r for r in rows if not r['active']],
            'errors': errors,
        }
    except Exception:  # noqa: BLE001
        return {'available': False}


def _code_tab() -> dict:
    out: dict = {'available': True}
    # Self-improvement recommendations (core immune system).
    try:
        from core.self_improvement.models import SiRecommendation

        recs = list(
            SiRecommendation.objects.filter(status='proposed').order_by('-impact_score')[:15]
        )
        out['recommendations'] = [
            {
                'title': r.title,
                'class_name': r.class_name,
                'impact': r.impact_score,
                'status': r.status,
            }
            for r in recs
        ]
        out['rec_total'] = SiRecommendation.objects.filter(status='proposed').count()
    except Exception:  # noqa: BLE001
        out['recommendations'] = None
    # Drift (intentional customizations diverged from canonical).
    with suppress(Exception):
        from core.self_improvement.models import SiCustomization

        out['drift_count'] = SiCustomization.objects.count()
    # Linda code proposals.
    try:
        from core.assistant.models import CodeProposal

        props = list(CodeProposal.objects.filter(status='draft').order_by('-created_at')[:15])
        out['proposals'] = [
            {
                'name': p.name,
                'kind': getattr(p, 'kind', ''),
                'status': p.status,
                'passed': p.passed,
                'findings': len(p.findings or []),
            }
            for p in props
        ]
        out['proposal_total'] = CodeProposal.objects.filter(status='draft').count()
    except Exception:  # noqa: BLE001
        out['proposals'] = None
    return out


def _content_tab() -> dict:
    out: dict = {'available': True}
    # SEO audit — lowest-scoring objects + averages.
    try:
        from django.db.models import Avg

        from plugins.installed.seo.models import SeoAuditResult

        low = list(SeoAuditResult.objects.order_by('score')[:20])
        out['low_seo'] = [
            {'score': a.score, 'issues': (a.issues or [])[:4], 'issue_count': len(a.issues or [])}
            for a in low
        ]
        agg = SeoAuditResult.objects.aggregate(avg=Avg('score'))
        out['seo_avg'] = round(agg['avg'] or 0, 1)
        out['seo_low_count'] = SeoAuditResult.objects.filter(score__lt=50).count()
        out['seo_total'] = SeoAuditResult.objects.count()
    except Exception:  # noqa: BLE001
        out['low_seo'] = None
    # Unresolved 404s.
    with suppress(Exception):
        from plugins.installed.seo.models import NotFoundLog

        out['notfound'] = [
            {'path': n.path, 'hits': n.hit_count}
            for n in NotFoundLog.objects.order_by('-hit_count')[:10]
        ]
    # Catalog content gaps.
    with suppress(Exception):
        from django.db.models import Q

        from plugins.installed.catalog.models import Product

        active = Product.objects.filter(status='active')
        out['catalog'] = {
            'total': active.count(),
            'missing_desc': active.filter(Q(description__isnull=True) | Q(description='')).count(),
        }
    return out


def _storefront_tab() -> dict:
    out: dict = {'available': True}
    # Core Web Vitals (real-user p75) via the seo beacon summary.
    with suppress(Exception):
        from plugins.installed.seo.views import _cwv_summary

        out['cwv'] = _cwv_summary()
    # Structured-data / discovery switches on the homepage.
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


def _improvements_tab() -> dict:
    out: dict = {'available': True}
    # Unread merchant insights (the AI pulse).
    with suppress(Exception):
        from plugins.installed.ai_assistant.models import MerchantInsight

        ins = list(MerchantInsight.objects.filter(is_read=False).order_by('-created_at')[:10])
        out['insights'] = [
            {
                'title': i.title,
                'type': getattr(i, 'insight_type', ''),
                'priority': getattr(i, 'priority', ''),
                'impact': getattr(i, 'estimated_impact', ''),
            }
            for i in ins
        ]
    # First-run setup checklist (reuse the dashboard filter).
    with suppress(Exception):
        from core.hooks import MorpheusEvents, hook_registry

        steps = hook_registry.filter(MorpheusEvents.DASHBOARD_SETUP_STEPS, value=[]) or []
        out['setup'] = [s for s in steps if isinstance(s, dict)]
    return out


def _extension_panels() -> list:
    """Cards contributed by other plugins via the BRAIN_PANELS filter (if any).
    Optional + forward-looking: plugins can `register_hook('brain.panels', ...)`
    to surface their own analysis without editing this plugin."""
    with suppress(Exception):
        from core.hooks import hook_registry

        panels = hook_registry.filter('brain.panels', value=[])
        return [p for p in (panels or []) if isinstance(p, dict)]
    return []


@staff_member_required
def brain(request):
    plugins = _plugins_tab()
    code = _code_tab()
    content = _content_tab()
    storefront = _storefront_tab()
    improvements = _improvements_tab()
    return render(
        request,
        'morpheus_brain/index.html',
        {
            'plugins': plugins,
            'code': code,
            'content': content,
            'storefront': storefront,
            'improvements': improvements,
            'extensions': _extension_panels(),
        },
    )
