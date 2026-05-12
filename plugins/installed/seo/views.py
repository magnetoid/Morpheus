"""SEO views — sitemap.xml, robots.txt, /llms.txt, AI feed, admin dashboard."""
from __future__ import annotations

import json

from morpheus.views import staff_member_required
from morpheus.views import HttpRequest, HttpResponse, JsonResponse
from morpheus.views import get_object_or_404, redirect, render

from plugins.installed.seo.services import (
    audit_all_products, audit_product, refresh_404_suggestions,
    render_ai_products_feed, render_llms_txt, render_product_markdown,
    render_robots_txt, render_sitemap_xml, site_settings, store_audit,
    suggest_redirect,
)


def sitemap_xml(request: HttpRequest) -> HttpResponse:
    return HttpResponse(render_sitemap_xml(), content_type='application/xml; charset=utf-8')


def robots_txt(request: HttpRequest) -> HttpResponse:
    return HttpResponse(render_robots_txt(), content_type='text/plain; charset=utf-8')


def llms_txt(request: HttpRequest) -> HttpResponse:
    s = site_settings()
    if not s.llms_txt_enabled:
        return HttpResponse('Not enabled.', status=404, content_type='text/plain')
    return HttpResponse(render_llms_txt(full=False), content_type='text/plain; charset=utf-8')


def llms_full_txt(request: HttpRequest) -> HttpResponse:
    s = site_settings()
    if not s.llms_txt_enabled:
        return HttpResponse('Not enabled.', status=404, content_type='text/plain')
    return HttpResponse(render_llms_txt(full=True), content_type='text/plain; charset=utf-8')


def ai_products_feed(request: HttpRequest) -> JsonResponse:
    s = site_settings()
    if not s.ai_shopping_feed_enabled:
        return JsonResponse({'error': 'Not enabled.'}, status=404)
    limit = int(request.GET.get('limit', 500) or 500)
    return JsonResponse(render_ai_products_feed(limit=limit))


def product_markdown(request: HttpRequest, slug: str) -> HttpResponse:
    """Markdown rendering of a product — the LLM-friendly view.

    Same data as the HTML PDP, no menu / no CSS / no script tags. Lets
    ChatGPT / Perplexity / Claude crawlers ingest the content without
    HTML parsing. Linked from /llms.txt + /llms-full.txt.
    """
    from plugins.installed.catalog.models import Product
    try:
        product = Product.objects.filter(slug=slug, status='active').first()
    except Exception:  # noqa: BLE001
        product = None
    if product is None:
        return HttpResponse('Not found.', status=404, content_type='text/plain; charset=utf-8')
    return HttpResponse(
        render_product_markdown(product),
        content_type='text/markdown; charset=utf-8',
    )


def image_sitemap_xml(request: HttpRequest) -> HttpResponse:
    """Image-only sitemap. Discovered by AI image-search engines for
    grounding (Google AI Overviews, Bing image search, Perplexity)."""
    from plugins.installed.seo.services import render_image_sitemap_xml
    return HttpResponse(
        render_image_sitemap_xml(),
        content_type='application/xml; charset=utf-8',
    )


def sitemap_index_xml(request: HttpRequest) -> HttpResponse:
    """Sitemap index — entry-point that lists every sub-sitemap.
    Search engines and AI crawlers prefer this over a flat sitemap
    once the catalog crosses ~50k URLs."""
    from plugins.installed.seo.services import render_sitemap_index_xml
    return HttpResponse(
        render_sitemap_index_xml(),
        content_type='application/xml; charset=utf-8',
    )


def news_sitemap_xml(request: HttpRequest) -> HttpResponse:
    """News sitemap — journal posts in the last 48h. Empty urlset
    when nothing is fresh, which is valid per Google's news spec."""
    from plugins.installed.seo.services import render_news_sitemap_xml
    return HttpResponse(
        render_news_sitemap_xml(),
        content_type='application/xml; charset=utf-8',
    )


def opensearch_xml(request: HttpRequest) -> HttpResponse:
    """OpenSearch description for browser tab-to-search engines."""
    from plugins.installed.seo.services import render_opensearch_xml
    return HttpResponse(
        render_opensearch_xml(),
        content_type='application/opensearchdescription+xml; charset=utf-8',
    )


def web_manifest(request: HttpRequest) -> JsonResponse:
    """PWA web app manifest. Browsers use this to install the store
    as a home-screen app + show themed window chrome."""
    from plugins.installed.seo.services import render_pwa_manifest
    return JsonResponse(render_pwa_manifest())


def indexnow_keyfile(request: HttpRequest, key: str) -> HttpResponse:
    """Serve the IndexNow key as plain text so api.indexnow.org can
    verify ownership of the host before accepting URL pushes.
    """
    from plugins.installed.seo.services import get_or_create_indexnow_key
    expected = get_or_create_indexnow_key()
    if key != expected:
        return HttpResponse('Unknown key.', status=404, content_type='text/plain; charset=utf-8')
    return HttpResponse(expected, content_type='text/plain; charset=utf-8')


def web_vitals_beacon(request: HttpRequest) -> JsonResponse:
    """Receive Real-User-Metrics from the storefront's web-vitals JS.

    Body: `{name, value, id, navigationType, rating, delta}` — the
    standard web-vitals.js payload. Stored as an `AuditEvent` row with
    event_type='cwv.report' so the dashboard can aggregate without a
    new model.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    try:
        body = json.loads(request.body.decode('utf-8') or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'error': 'bad json'}, status=400)
    metric = (body.get('name') or '').upper()
    if metric not in ('LCP', 'INP', 'CLS', 'FCP', 'TTFB', 'FID'):
        return JsonResponse({'error': 'unknown metric'}, status=400)
    try:
        from core.audit.services import record
        record(
            event_type='cwv.report',
            target=(body.get('url') or request.headers.get('Referer') or '')[:200],
            metadata={
                'metric': metric,
                'value': float(body.get('value') or 0.0),
                'rating': body.get('rating', ''),
                'nav_type': body.get('navigationType', ''),
                'delta': float(body.get('delta') or 0.0),
                'page_id': body.get('id', ''),
            },
            request_id=getattr(request, 'request_id', '') or '',
        )
    except Exception:  # noqa: BLE001
        pass  # never let beacon failures noise the request
    return JsonResponse({'ok': True})


# ─────────────────────────────────────────────────────────────────────────────
# Admin dashboard pages
# ─────────────────────────────────────────────────────────────────────────────


@staff_member_required
def seo_overview(request):
    from plugins.installed.seo.models import (
        NotFoundLog, Redirect, SeoAuditResult, SeoMeta, TrackedKeyword,
    )
    cwv = _cwv_summary()
    return render(request, 'seo/overview.html', {
        'site_settings': site_settings(),
        'meta_count': SeoMeta.objects.count(),
        'redirect_count': Redirect.objects.filter(is_active=True).count(),
        'not_found_count': NotFoundLog.objects.filter(is_resolved=False).count(),
        'tracked_keywords': TrackedKeyword.objects.count(),
        'audit_count': SeoAuditResult.objects.count(),
        'lowest_scores': SeoAuditResult.objects.order_by('score')[:10],
        'cwv': cwv,
        'active_nav': 'seo',
    })


def _cwv_summary() -> dict:
    """Aggregate the last 1000 web-vitals beacon reports into p75 per
    metric — the same threshold Google uses to decide pass/fail.

    Source: AuditEvent rows with event_type='cwv.report'. No new model.
    """
    out = {'lcp': None, 'inp': None, 'cls': None, 'samples': 0}
    try:
        from core.audit.models import AuditEvent
        rows = list(
            AuditEvent.objects
            .filter(event_type='cwv.report')
            .order_by('-created_at')[:1000]
            .values_list('metadata', flat=True)
        )
        if not rows:
            return out
        out['samples'] = len(rows)
        for metric_key, metric_name in (('lcp', 'LCP'), ('inp', 'INP'), ('cls', 'CLS')):
            values = sorted([
                float(m.get('value') or 0.0)
                for m in rows
                if (m or {}).get('metric') == metric_name
            ])
            if values:
                p75_idx = int(0.75 * (len(values) - 1))
                out[metric_key] = values[p75_idx]
    except Exception:  # noqa: BLE001
        pass
    return out


@staff_member_required
def seo_settings_page(request):
    from plugins.installed.seo.models import SiteSeoSettings
    s = site_settings()
    if request.method == 'POST':
        for field in (
            'organization_name', 'organization_logo_url', 'default_og_image',
            'twitter_handle', 'twitter_card_default',
            'facebook_url', 'instagram_url', 'linkedin_url',
            'youtube_url', 'tiktok_url',
            'google_site_verification', 'bing_verification',
            'pinterest_verification', 'facebook_domain_verification',
            'title_template', 'llms_txt_intro',
        ):
            setattr(s, field, request.POST.get(field, '') or '')
        for field in ('enable_sitelinks_search', 'llms_txt_enabled', 'ai_shopping_feed_enabled'):
            setattr(s, field, bool(request.POST.get(field)))
        for field, default in (('title_max_length', 60), ('description_max_length', 155)):
            try:
                setattr(s, field, int(request.POST.get(field, default) or default))
            except ValueError:
                pass
        params = (request.POST.get('noindex_query_params', '') or '').strip()
        s.noindex_query_params = [p.strip() for p in params.split(',') if p.strip()]
        # AI crawler matrix — POST keys are crawler_<UA_lower>=on / missing.
        from plugins.installed.seo.services import AI_CRAWLERS
        from plugins.registry import plugin_registry
        seo_plugin = plugin_registry.get('seo')
        if seo_plugin is not None:
            policy = {
                ua.lower(): (request.POST.get(f'crawler_{ua.lower()}') == 'on')
                for ua, _label, _kind in AI_CRAWLERS
            }
            seo_plugin.set_config('ai_crawler_policy', policy)
        if not s.pk:
            s.save()
        else:
            s.save()
        return redirect('seo_dashboard:settings')

    # Render context — pre-compute the crawler matrix so the template
    # only iterates a flat list.
    from plugins.installed.seo.services import AI_CRAWLERS, get_ai_crawler_policy
    policy_now = get_ai_crawler_policy()
    crawler_rows = [
        {
            'ua': ua, 'label': label, 'kind': kind,
            'allowed': policy_now.get(ua.lower(), True),
        }
        for ua, label, kind in AI_CRAWLERS
    ]
    return render(request, 'seo/settings.html', {
        's': s, 'active_nav': 'seo',
        'crawler_rows': crawler_rows,
    })


@staff_member_required
def not_found_log(request):
    from plugins.installed.seo.models import NotFoundLog
    refresh_404_suggestions()
    rows = NotFoundLog.objects.filter(is_resolved=False).order_by('-hit_count')[:200]
    return render(request, 'seo/not_found.html', {'rows': rows, 'active_nav': 'seo'})


@staff_member_required
def not_found_create_redirect(request, log_id):
    from plugins.installed.seo.models import NotFoundLog, Redirect
    log = get_object_or_404(NotFoundLog, id=log_id)
    if request.method == 'POST':
        target = (request.POST.get('to_path') or log.suggested_target or '').strip()
        if target:
            Redirect.objects.update_or_create(
                from_path=log.path,
                defaults={'to_path': target, 'status_code': 301, 'is_active': True,
                          'note': f'Auto-created from 404 (hits: {log.hit_count})'},
            )
            log.is_resolved = True
            log.save(update_fields=['is_resolved'])
    return redirect('seo_dashboard:not_found')


@staff_member_required
def audit_page(request):
    if request.method == 'POST':
        n = audit_all_products(limit=500)
        return JsonResponse({'audited': n})
    from plugins.installed.seo.models import SeoAuditResult
    rows = SeoAuditResult.objects.order_by('score')[:100]
    return render(request, 'seo/audit.html', {'rows': rows, 'active_nav': 'seo'})


@staff_member_required
def keywords_page(request):
    from plugins.installed.seo.models import TrackedKeyword
    if request.method == 'POST':
        kw = (request.POST.get('keyword') or '').strip()
        if kw:
            TrackedKeyword.objects.get_or_create(
                keyword=kw, locale=request.POST.get('locale', 'en-US') or 'en-US',
                defaults={
                    'target_url': (request.POST.get('target_url') or '').strip(),
                    'notes': (request.POST.get('notes') or '').strip(),
                },
            )
        return redirect('seo_dashboard:keywords')
    rows = TrackedKeyword.objects.all().order_by('keyword')
    return render(request, 'seo/keywords.html', {'rows': rows, 'active_nav': 'seo'})


@staff_member_required
def bulk_meta(request):
    """Bulk-edit SEO titles + descriptions across products."""
    from django.contrib.contenttypes.models import ContentType
    from plugins.installed.catalog.models import Product
    from plugins.installed.seo.models import SeoMeta

    if request.method == 'POST':
        ct = ContentType.objects.get_for_model(Product)
        n = 0
        for key, val in request.POST.items():
            if not key.startswith('meta_'):
                continue
            try:
                _, pk, field = key.split('_', 2)
            except ValueError:
                continue
            if field not in ('title', 'description'):
                continue
            meta, _ = SeoMeta.objects.get_or_create(content_type=ct, object_id=pk)
            setattr(meta, field, (val or '')[:320])
            meta.auto_filled = False
            meta.save(update_fields=[field, 'auto_filled', 'updated_at'])
            n += 1
        return redirect('seo_dashboard:bulk_meta')

    products = list(Product.objects.filter(status='active').order_by('name')[:200])
    ct = ContentType.objects.get_for_model(Product)
    metas = {
        m.object_id: m
        for m in SeoMeta.objects.filter(
            content_type=ct, object_id__in=[str(p.pk) for p in products],
        )
    }
    rows = []
    for p in products:
        m = metas.get(str(p.pk))
        rows.append({
            'product': p,
            'title': m.title if m else '',
            'description': m.description if m else '',
        })
    return render(request, 'seo/bulk_meta.html', {'rows': rows, 'active_nav': 'seo'})
