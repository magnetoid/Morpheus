"""SEO views — sitemap.xml, robots.txt, /llms.txt, AI feed, admin dashboard."""

# ruff: noqa: PLC0415, I001, S110, S112, SIM105, SIM114, SIM115, F401, UP017, PLR0911, PLR0912, PLR0915
# Views resolve optional plugins (catalog, cms, inventory) lazily inside
# each handler so a disabled plugin never breaks an unrelated page, and
# the dashboard handlers are deliberately long, flat request/response
# flows. Same convention as services/jsonld.py. (Pre-existing module-top
# imports flagged unused — audit_product / store_audit / suggest_redirect
# — are left untouched per the surgical-changes rule.)

from __future__ import annotations

import json

from django.contrib import messages
from django.utils.http import http_date

from morpheus.views import staff_member_required
from morpheus.views import HttpRequest, HttpResponse, JsonResponse
from morpheus.views import get_object_or_404, redirect, render

from plugins.installed.seo.services import (
    audit_all_products,
    audit_product,
    cwv_summary,
    refresh_404_suggestions,
    render_agents_md,
    render_ai_products_feed,
    render_llms_txt,
    render_product_markdown,
    render_robots_txt,
    render_sitemap_xml,
    site_settings,
    store_audit,
    suggest_redirect,
)
from plugins.installed.seo.services.feeds import (
    render_journal_atom,
    render_journal_rss,
)


def _cache_headers(response: HttpResponse, last_modified=None) -> HttpResponse:
    """Apply the shared public-crawler cache policy to a response.

    Every public SEO surface (sitemaps, robots.txt, llms.txt, AI feed,
    OpenSearch) gets the same Cache-Control values so Cloudflare's edge
    + browser intermediaries cache them uniformly: 15 min on the client,
    1 h on the shared cache.

    ``last_modified`` is optional — pass a ``datetime`` (or any value
    accepted by Django's ``http_date()``) when the surface has a reliable
    "content changed at" timestamp. Skip when there's no good source.
    """
    response['Cache-Control'] = 'public, max-age=900, s-maxage=3600'
    if last_modified is not None:
        try:
            if hasattr(last_modified, 'timestamp'):
                response['Last-Modified'] = http_date(last_modified.timestamp())
            else:
                # Already a unix timestamp / epoch number.
                response['Last-Modified'] = http_date(float(last_modified))
        except Exception:  # noqa: BLE001 — never let header math break the response
            pass
    return response


def _sitemap_last_modified():
    """Best-effort last-modified for sitemap surfaces.

    Reads ``sitemap_counts()['last_modified']`` (ISO 8601) and converts
    it to a ``datetime``. Returns ``None`` when nothing reliable is
    available — callers then omit the header.
    """
    try:
        from datetime import datetime
        from plugins.installed.seo.services import sitemap_counts

        raw = sitemap_counts().get('last_modified') or ''
        if not raw:
            return None
        # ``datetime.fromisoformat`` handles "+00:00" suffixes; strip a
        # trailing "Z" which it doesn't accept before 3.11.
        if raw.endswith('Z'):
            raw = raw[:-1] + '+00:00'
        return datetime.fromisoformat(raw)
    except Exception:  # noqa: BLE001
        return None


def sitemap_xml(request: HttpRequest) -> HttpResponse:
    resp = HttpResponse(render_sitemap_xml(), content_type='application/xml; charset=utf-8')
    return _cache_headers(resp, last_modified=_sitemap_last_modified())


def robots_txt(request: HttpRequest) -> HttpResponse:
    resp = HttpResponse(render_robots_txt(), content_type='text/plain; charset=utf-8')
    # robots.txt rarely changes — use the SiteSeoSettings.updated_at
    # signal so crawlers know when the merchant flipped a toggle.
    return _cache_headers(resp, last_modified=getattr(site_settings(), 'updated_at', None))


def llms_txt(request: HttpRequest) -> HttpResponse:
    s = site_settings()
    if not s.llms_txt_enabled:
        return HttpResponse('Not enabled.', status=404, content_type='text/plain')
    resp = HttpResponse(render_llms_txt(full=False), content_type='text/plain; charset=utf-8')
    return _cache_headers(resp, last_modified=getattr(s, 'updated_at', None))


def llms_full_txt(request: HttpRequest) -> HttpResponse:
    s = site_settings()
    if not s.llms_txt_enabled:
        return HttpResponse('Not enabled.', status=404, content_type='text/plain')
    resp = HttpResponse(render_llms_txt(full=True), content_type='text/plain; charset=utf-8')
    return _cache_headers(resp, last_modified=getattr(s, 'updated_at', None))


def agents_md(request: HttpRequest) -> HttpResponse:
    """/agents.md — the agent-onboarding manifest (gated by the same
    expose-to-AI toggle as llms.txt)."""
    s = site_settings()
    if not s.llms_txt_enabled:
        return HttpResponse('Not enabled.', status=404, content_type='text/plain')
    resp = HttpResponse(render_agents_md(), content_type='text/markdown; charset=utf-8')
    return _cache_headers(resp, last_modified=getattr(s, 'updated_at', None))


def journal_rss(request: HttpRequest) -> HttpResponse:
    """RSS 2.0 feed for /journal/. Top 50 published posts, ordered by publish_at."""
    resp = HttpResponse(
        render_journal_rss(),
        content_type='application/rss+xml; charset=utf-8',
    )
    return _cache_headers(resp, last_modified=_sitemap_last_modified())


def journal_atom(request: HttpRequest) -> HttpResponse:
    """Atom 1.0 feed for /journal/. Same source set as the RSS feed."""
    resp = HttpResponse(
        render_journal_atom(),
        content_type='application/atom+xml; charset=utf-8',
    )
    return _cache_headers(resp, last_modified=_sitemap_last_modified())


def ai_products_feed(request: HttpRequest) -> JsonResponse:
    s = site_settings()
    if not s.ai_shopping_feed_enabled:
        return JsonResponse({'error': 'Not enabled.'}, status=404)
    try:
        limit = int(request.GET.get('limit', 1000) or 1000)
    except (TypeError, ValueError):
        limit = 1000
    try:
        offset = int(request.GET.get('offset', 0) or 0)
    except (TypeError, ValueError):
        offset = 0
    limit = max(1, min(limit, 1000))
    offset = max(0, offset)
    resp = JsonResponse(render_ai_products_feed(limit=limit, offset=offset))
    return _cache_headers(resp, last_modified=_sitemap_last_modified())


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
    grounding (Google AI Overviews, Bing image search, Perplexity).

    Respects PluginConfig['seo']['image_sitemap_enabled'] — when False,
    returns a 404 so search engines stop fetching it.
    """
    from plugins.installed.seo.services import render_image_sitemap_xml

    if not _seo_flag('image_sitemap_enabled', True):
        from django.http import Http404

        raise Http404('Image sitemap disabled by store settings.')
    resp = HttpResponse(
        render_image_sitemap_xml(),
        content_type='application/xml; charset=utf-8',
    )
    return _cache_headers(resp, last_modified=_sitemap_last_modified())


def sitemap_index_xml(request: HttpRequest) -> HttpResponse:
    """Sitemap index — entry-point that lists every sub-sitemap.
    Search engines and AI crawlers prefer this over a flat sitemap
    once the catalog crosses ~50k URLs."""
    from plugins.installed.seo.services import render_sitemap_index_xml

    resp = HttpResponse(
        render_sitemap_index_xml(),
        content_type='application/xml; charset=utf-8',
    )
    return _cache_headers(resp, last_modified=_sitemap_last_modified())


def news_sitemap_xml(request: HttpRequest) -> HttpResponse:
    """News sitemap — journal posts in the last 48h. Empty urlset
    when nothing is fresh, which is valid per Google's news spec.

    Respects PluginConfig['seo']['news_sitemap_enabled'] — off by
    default because Google News has specific eligibility rules and
    serving an empty-news sitemap to crawlers is wasteful.
    """
    from plugins.installed.seo.services import render_news_sitemap_xml

    if not _seo_flag('news_sitemap_enabled', False):
        from django.http import Http404

        raise Http404('News sitemap disabled by store settings.')
    resp = HttpResponse(
        render_news_sitemap_xml(),
        content_type='application/xml; charset=utf-8',
    )
    return _cache_headers(resp, last_modified=_sitemap_last_modified())


def _seo_flag(key: str, default: bool) -> bool:
    """Read a boolean SEO plugin config value defensively."""
    try:
        from plugins.registry import plugin_registry

        plugin = None
        for attr in ('get', 'get_plugin'):
            fn = getattr(plugin_registry, attr, None)
            if callable(fn):
                try:
                    plugin = fn('seo')
                except Exception:  # noqa: BLE001
                    continue
                if plugin is not None:
                    break
        if plugin is None:
            return default
        return bool(plugin.get_config_value(key, default))
    except Exception:  # noqa: BLE001
        return default


def _maybe_ping_sitemap_change() -> None:
    """Notify Google + Bing + IndexNow when the sitemap changed.

    Driven by PluginConfig['seo']['ping_google_on_sitemap_change']
    (default True). Async — spawn a daemon thread so the merchant's
    POST returns immediately. Ping failures are logged and swallowed
    (search-engine pings are best-effort by design).
    """
    if not _seo_flag('ping_google_on_sitemap_change', True):
        return
    try:
        from plugins.installed.seo.services import _site_base_url, ping_indexnow

        base = _site_base_url().rstrip('/')
        # Ping the sitemap index, not the flat sitemap — crawlers
        # discover every sub-sitemap from the index in one fetch.
        sitemap_url = f'{base}/sitemap-index.xml'
        import threading

        threading.Thread(
            target=ping_indexnow,
            args=([sitemap_url],),
            daemon=True,
        ).start()
    except Exception:  # noqa: BLE001
        pass


def opensearch_xml(request: HttpRequest) -> HttpResponse:
    """OpenSearch description for browser tab-to-search engines."""
    from plugins.installed.seo.services import render_opensearch_xml

    resp = HttpResponse(
        render_opensearch_xml(),
        content_type='application/opensearchdescription+xml; charset=utf-8',
    )
    # OpenSearch descriptors change only when site_settings change.
    return _cache_headers(resp, last_modified=getattr(site_settings(), 'updated_at', None))


def image_variant(request: HttpRequest, fmt: str, width: int, path: str) -> HttpResponse:
    """Serve a resized WebP/AVIF variant of an image under MEDIA_ROOT.

    URL shape: /img/<fmt>/<width>/<media-relative-path>
    Whitelisted widths/formats only. Cached on disk after first hit
    and returned with a 1-year immutable Cache-Control so Cloudflare /
    browser cache pin it forever (variants are content-addressed).
    """
    from plugins.installed.seo.services import (
        parse_image_variant_path,
        generate_image_variant,
    )

    resolved = parse_image_variant_path(fmt, width, path)
    if resolved is None:
        return HttpResponse('Not found.', status=404, content_type='text/plain; charset=utf-8')
    src_abs, cache_abs = resolved
    try:
        generate_image_variant(src_abs, cache_abs, width=width, fmt=fmt)
    except Exception:  # noqa: BLE001 — fall through to source as fallback
        from django.http import FileResponse

        return FileResponse(open(src_abs, 'rb'))
    from django.http import FileResponse

    mime = 'image/avif' if fmt == 'avif' else 'image/webp'
    resp = FileResponse(open(cache_abs, 'rb'), content_type=mime)
    resp['Cache-Control'] = 'public, max-age=31536000, immutable'
    return resp


def security_txt(request: HttpRequest) -> HttpResponse:
    """Serve /.well-known/security.txt per RFC 9116.

    Contact email pulled from core StoreSettings; falls back to a
    safe placeholder so the file is always well-formed. Expires in
    one year from now so security researchers see a fresh signal.
    """
    from datetime import datetime, timedelta, timezone as dt_tz

    contact = 'security@example.com'
    try:
        from core.models import StoreSettings

        ss = StoreSettings.objects.first()
        if ss and ss.contact_email:
            contact = ss.contact_email
    except Exception:  # noqa: BLE001
        pass
    try:
        from plugins.installed.seo.services import _site_base_url

        base = _site_base_url().rstrip('/')
    except Exception:  # noqa: BLE001
        base = ''
    expires = (datetime.now(dt_tz.utc) + timedelta(days=365)).strftime('%Y-%m-%dT%H:%M:%SZ')
    body = '\n'.join(
        [
            f'Contact: mailto:{contact}',
            f'Expires: {expires}',
            'Preferred-Languages: en',
            f'Policy: {base}/contact/',
            f'Hiring: {base}/about/',
            '',
        ]
    )
    resp = HttpResponse(body, content_type='text/plain; charset=utf-8')
    resp['Cache-Control'] = 'public, max-age=86400'
    return resp


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
    from datetime import timedelta

    from django.contrib.contenttypes.models import ContentType
    from django.utils import timezone

    from plugins.installed.catalog.models import Product
    from plugins.installed.seo.models import (
        NotFoundLog,
        Redirect,
        SeoAuditResult,
        SeoMeta,
        TrackedKeyword,
    )

    cwv = cwv_summary()

    # Outcome ratio: % of active Products with a complete SeoMeta
    # (non-empty title AND description). Zero-active-products falls
    # back to 0% so the tile doesn't divide-by-zero.
    product_ct = ContentType.objects.get_for_model(Product)
    active_total = Product.objects.filter(status='active').count()
    if active_total:
        active_ids = list(Product.objects.filter(status='active').values_list('id', flat=True))
        # SeoMeta.object_id is a CharField — match the cast Django uses
        # at write time (str(pk)).
        meta_complete = (
            SeoMeta.objects.filter(
                content_type=product_ct,
                object_id__in=[str(pid) for pid in active_ids],
            )
            .exclude(title='')
            .exclude(description='')
            .count()
        )
        meta_complete_pct = int(round(100 * meta_complete / active_total))
    else:
        meta_complete = 0
        meta_complete_pct = 0

    # 404 momentum — open rows seen in the last 7 days, plus the
    # delta vs the previous 7-day window so the merchant can tell
    # if things are getting worse.
    now = timezone.now()
    week_ago = now - timedelta(days=7)
    two_weeks_ago = now - timedelta(days=14)
    not_found_7d = NotFoundLog.objects.filter(
        first_seen_at__gte=week_ago,
        is_resolved=False,
    ).count()
    not_found_prev_7d = NotFoundLog.objects.filter(
        first_seen_at__gte=two_weeks_ago,
        first_seen_at__lt=week_ago,
        is_resolved=False,
    ).count()
    not_found_7d_delta = not_found_7d - not_found_prev_7d

    # Keywords currently in the top 10 of the SERP.
    # Model field is `last_position` (NOT `last_known_position`).
    keywords_in_top10 = TrackedKeyword.objects.filter(
        last_position__isnull=False,
        last_position__lte=10,
    ).count()

    return render(
        request,
        'seo/overview.html',
        {
            'site_settings': site_settings(),
            'meta_count': SeoMeta.objects.count(),
            'meta_complete': meta_complete,
            'meta_complete_pct': meta_complete_pct,
            'active_product_total': active_total,
            'redirect_count': Redirect.objects.filter(is_active=True).count(),
            'not_found_count': NotFoundLog.objects.filter(is_resolved=False).count(),
            'not_found_7d': not_found_7d,
            'not_found_7d_delta': not_found_7d_delta,
            'tracked_keywords': TrackedKeyword.objects.count(),
            'keywords_in_top10': keywords_in_top10,
            'audit_count': SeoAuditResult.objects.count(),
            'lowest_scores': SeoAuditResult.objects.order_by('score')[:10],
            'cwv': cwv,
            'active_nav': 'seo',
        },
    )


@staff_member_required
def seo_settings_page(request):
    from plugins.installed.seo.models import SiteSeoSettings

    s = site_settings()
    if request.method == 'POST':
        # Image optimization moved to /dashboard/settings/caching/ (ADR 0005).
        for field in (
            'organization_name',
            'organization_logo_url',
            'default_og_image',
            'twitter_handle',
            'twitter_card_default',
            'facebook_url',
            'instagram_url',
            'linkedin_url',
            'youtube_url',
            'tiktok_url',
            'google_site_verification',
            'bing_verification',
            'pinterest_verification',
            'facebook_domain_verification',
            'title_template',
            'llms_txt_intro',
        ):
            setattr(s, field, request.POST.get(field, '') or '')
        for field in (
            'enable_sitelinks_search',
            'llms_txt_enabled',
            'ai_shopping_feed_enabled',
            'ai_answer_block_enabled',
            'jsonld_organization',
            'jsonld_website',
            'jsonld_product',
            'jsonld_reviews',
        ):
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
            'ua': ua,
            'label': label,
            'kind': kind,
            'allowed': policy_now.get(ua.lower(), True),
        }
        for ua, label, kind in AI_CRAWLERS
    ]
    # Group by kind for the 2026 training-vs-retrieval split.
    crawler_groups = [
        {
            'kind': 'search',
            'title': 'Retrieval bots — power AI Overviews + ChatGPT/Perplexity citations',
            'hint': 'These bots fetch content at answer-time. Leaving them allowed is how your store shows up in AI answers.',
            'rows': [r for r in crawler_rows if r['kind'] == 'search'],
        },
        {
            'kind': 'user',
            'title': 'User-triggered fetchers — invoked when a person asks the AI to browse',
            'hint': 'User-instructed fetches (e.g. ChatGPT browse, Claude search). Usually safe to allow.',
            'rows': [r for r in crawler_rows if r['kind'] == 'user'],
        },
        {
            'kind': 'training',
            'title': 'Training crawlers — feed LLM pre-training corpora',
            'hint': "Disallow these if you don't want your content in the next round of model training. Does not affect AI citations.",
            'rows': [r for r in crawler_rows if r['kind'] == 'training'],
        },
    ]
    return render(
        request,
        'seo/settings.html',
        {
            's': s,
            'active_nav': 'seo',
            'crawler_rows': crawler_rows,
            'crawler_groups': crawler_groups,
        },
    )


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
                defaults={
                    'to_path': target,
                    'status_code': 301,
                    'is_active': True,
                    'note': f'Auto-created from 404 (hits: {log.hit_count})',
                },
            )
            log.is_resolved = True
            log.save(update_fields=['is_resolved'])
    return redirect('seo_dashboard:not_found')


@staff_member_required
def audit_page(request):
    if request.method == 'POST':
        n = audit_all_products(limit=500)
        # Redirect after POST so a browser refresh doesn't re-trigger
        # the audit, and the merchant sees the refreshed table.
        messages.success(request, f'Audited {n} products.')
        return redirect('seo_dashboard:audit')
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
                keyword=kw,
                locale=request.POST.get('locale', 'en-US') or 'en-US',
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

    from django.core.paginator import Paginator
    from django.db.models import Q

    q = (request.GET.get('q') or '').strip()
    missing = (request.GET.get('missing') or '').strip()

    qs = Product.objects.filter(status='active').order_by('name')
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(slug__icontains=q))

    if missing in ('desc', 'title', 'both'):
        # Narrow to products whose SeoMeta is missing the requested
        # field. Easier in two passes than a multi-table join with a
        # nullable GenericForeignKey.
        ct = ContentType.objects.get_for_model(Product)
        all_metas = SeoMeta.objects.filter(content_type=ct).values(
            'object_id',
            'title',
            'description',
        )
        meta_by_pk = {m['object_id']: m for m in all_metas}
        keep = []
        for p in qs.only('id', 'name', 'slug'):
            m = meta_by_pk.get(str(p.pk))
            has_title = bool(m and (m.get('title') or '').strip())
            has_desc = bool(m and (m.get('description') or '').strip())
            if missing == 'title' and not has_title:
                keep.append(p.pk)
            elif missing == 'desc' and not has_desc:
                keep.append(p.pk)
            elif missing == 'both' and not has_title and not has_desc:
                keep.append(p.pk)
        qs = Product.objects.filter(pk__in=keep).order_by('name')

    paginator = Paginator(qs, 50)
    page_number = request.GET.get('page') or 1
    page_obj = paginator.get_page(page_number)
    products = list(page_obj.object_list)

    ct = ContentType.objects.get_for_model(Product)
    metas = {
        m.object_id: m
        for m in SeoMeta.objects.filter(
            content_type=ct,
            object_id__in=[str(p.pk) for p in products],
        )
    }
    rows = []
    for p in products:
        m = metas.get(str(p.pk))
        rows.append(
            {
                'product': p,
                'title': m.title if m else '',
                'description': m.description if m else '',
            }
        )
    return render(
        request,
        'seo/bulk_meta.html',
        {
            'rows': rows,
            'page_obj': page_obj,
            'paginator': paginator,
            'q': q,
            'missing': missing,
            's': site_settings(),
            'active_nav': 'seo',
        },
    )


@staff_member_required
def sitemap_page(request):
    """Sitemap dashboard — single page for every sitemap surface,
    manual entries CRUD, IndexNow status, toggles, and a validate
    button. No new models; reuses iter_sitemap_entries() +
    SitemapEntry + SiteSeoSettings + seo plugin config.
    """
    from decimal import Decimal, InvalidOperation
    from morpheus.views import HttpResponseRedirect
    from plugins.installed.seo.models import SitemapEntry, SiteSeoSettings
    from plugins.installed.seo.services import (
        _site_base_url,
        get_or_create_indexnow_key,
        iter_sitemap_entries,
        ping_indexnow,
        sitemap_counts,
    )
    from plugins.registry import plugin_registry

    seo_plugin = plugin_registry.get('seo')

    def _plugin_get(key, default):
        try:
            return seo_plugin.get_config_value(key, default) if seo_plugin else default
        except Exception:  # noqa: BLE001
            return default

    def _plugin_set(key, value):
        if seo_plugin is not None:
            try:
                seo_plugin.set_config(key, value)
            except Exception:  # noqa: BLE001
                pass

    flash = ''
    flash_kind = 'ok'

    if request.method == 'POST':
        action = (request.POST.get('action') or '').strip()

        if action == 'add_entry':
            location = (request.POST.get('location') or '').strip()[:500]
            if location:
                try:
                    priority = Decimal(request.POST.get('priority') or '0.5')
                except InvalidOperation:
                    priority = Decimal('0.5')
                SitemapEntry.objects.create(
                    location=location,
                    changefreq=(request.POST.get('changefreq') or 'weekly').strip(),
                    priority=priority,
                    is_active=request.POST.get('is_active') == 'on',
                )
                _maybe_ping_sitemap_change()
            return HttpResponseRedirect('/dashboard/seo/sitemap/')

        if action == 'edit_entry':
            entry_id = (request.POST.get('id') or '').strip()
            if entry_id:
                location = (request.POST.get('location') or '').strip()[:500]
                try:
                    priority = Decimal(request.POST.get('priority') or '0.5')
                except InvalidOperation:
                    priority = Decimal('0.5')
                SitemapEntry.objects.filter(pk=entry_id).update(
                    location=location,
                    changefreq=(request.POST.get('changefreq') or 'weekly').strip(),
                    priority=priority,
                    is_active=request.POST.get('is_active') == 'on',
                )
                _maybe_ping_sitemap_change()
            return HttpResponseRedirect('/dashboard/seo/sitemap/')

        if action == 'delete_entry':
            SitemapEntry.objects.filter(pk=request.POST.get('id') or '').delete()
            _maybe_ping_sitemap_change()
            return HttpResponseRedirect('/dashboard/seo/sitemap/')

        if action == 'save_toggles':
            s = site_settings()
            for field in (
                'llms_txt_enabled',
                'ai_shopping_feed_enabled',
                'enable_sitelinks_search',
            ):
                setattr(s, field, bool(request.POST.get(field)))
            s.save()
            _plugin_set('indexnow_enabled', bool(request.POST.get('indexnow_enabled')))
            _plugin_set('news_sitemap_enabled', bool(request.POST.get('news_sitemap_enabled')))
            _plugin_set('image_sitemap_enabled', bool(request.POST.get('image_sitemap_enabled')))
            return HttpResponseRedirect('/dashboard/seo/sitemap/?saved=1')

        if action == 'ping_sitemap':
            base = _site_base_url().rstrip('/')
            result = ping_indexnow([f'{base}/sitemap.xml'])
            ok = result.get('ok')
            status = result.get('status') or result.get('error') or '—'
            return HttpResponseRedirect(
                f'/dashboard/seo/sitemap/?ping={"ok" if ok else "err"}&status={status}'
            )

        if action == 'regenerate':
            from plugins.installed.seo.services import regenerate_sitemap

            res = regenerate_sitemap(triggered_by='dashboard')
            total = (res.get('counts') or {}).get('total', 0)
            return HttpResponseRedirect(
                f'/dashboard/seo/sitemap/?regen=ok&total={total}'
                f'&purged={res.get("purged_zones", 0)}&pinged={int(bool(res.get("pinged")))}'
            )

        if action == 'ping_url':
            target = (request.POST.get('target_url') or '').strip()
            if target:
                result = ping_indexnow([target])
                ok = result.get('ok')
                status = result.get('status') or result.get('error') or '—'
                return HttpResponseRedirect(
                    f'/dashboard/seo/sitemap/?ping={"ok" if ok else "err"}&status={status}'
                )
            return HttpResponseRedirect('/dashboard/seo/sitemap/')

        if action == 'validate':
            import requests as _requests

            errors = []
            ok_n = 0
            sample = []
            for i, e in enumerate(iter_sitemap_entries()):
                if i >= 25:
                    break
                sample.append(e['loc'])
            for url in sample:
                try:
                    r = _requests.head(url, timeout=3, allow_redirects=True)
                    if 200 <= r.status_code < 400:
                        ok_n += 1
                    else:
                        errors.append({'url': url, 'status': r.status_code})
                except Exception as exc:  # noqa: BLE001
                    errors.append({'url': url, 'status': str(exc)[:40]})
            request.session['sitemap_validate'] = {
                'checked': len(sample),
                'ok': ok_n,
                'errors': errors[:10],
            }
            return HttpResponseRedirect('/dashboard/seo/sitemap/?validated=1')

    # GET render path.
    s = site_settings()
    counts = sitemap_counts()
    base = _site_base_url().rstrip('/')
    key = get_or_create_indexnow_key()
    redacted_key = (key[:4] + '…' + key[-4:]) if key and len(key) >= 8 else key

    edit_id = (request.GET.get('edit') or '').strip()
    edit_entry = None
    entries = list(SitemapEntry.objects.all().order_by('location'))
    if edit_id:
        edit_entry = next((e for e in entries if str(e.pk) == edit_id), None)

    surfaces = [
        {
            'label': 'Sitemap index',
            'path': '/sitemap-index.xml',
            'desc': 'Discovery doc — points crawlers at every sub-sitemap.',
        },
        {
            'label': 'Main sitemap',
            'path': '/sitemap.xml',
            'desc': f'{counts["total"]} URLs (products + categories + journal + manual).',
        },
        {
            'label': 'Image sitemap',
            'path': '/sitemap-images.xml',
            'desc': 'Image URLs for Google Image + AI Overview discovery.',
        },
        {
            'label': 'News sitemap',
            'path': '/sitemap-news.xml',
            'desc': 'Recent journal posts (window configurable via news_sitemap_max_age_hours; default 7 days).',
        },
        {
            'label': 'robots.txt',
            'path': '/robots.txt',
            'desc': 'Per-bot allow/disallow + sitemap pointers.',
        },
        {
            'label': '/llms.txt',
            'path': '/llms.txt',
            'desc': 'LLM-friendly site map (OpenAI/Anthropic/Perplexity/Google).',
        },
        {
            'label': '/llms-full.txt',
            'path': '/llms-full.txt',
            'desc': 'Full content dump for LLM ingestion.',
        },
        {
            'label': 'AI products feed',
            'path': '/ai/products.json',
            'desc': 'schema.org Product feed for AI shopping crawlers.',
        },
        {
            'label': 'OpenSearch',
            'path': '/opensearch.xml',
            'desc': 'Browser tab → search engine descriptor.',
        },
        {
            'label': 'Web app manifest',
            'path': '/manifest.webmanifest',
            'desc': 'PWA manifest — now owned by the pwa plugin (install + offline).',
        },
        {
            'label': 'IndexNow key',
            'path': f'/{key}.txt' if key else '',
            'desc': 'Bing/Yandex verification key.',
        },
    ]

    return render(
        request,
        'seo/sitemap.html',
        {
            'active_nav': 'seo',
            's': s,
            'base': base,
            'counts': counts,
            'surfaces': surfaces,
            'entries': entries,
            'edit_entry': edit_entry,
            'indexnow_key_redacted': redacted_key,
            'indexnow_enabled': bool(_plugin_get('indexnow_enabled', True)),
            'news_sitemap_enabled': bool(_plugin_get('news_sitemap_enabled', True)),
            'image_sitemap_enabled': bool(_plugin_get('image_sitemap_enabled', True)),
            'last_ping': request.GET.get('ping'),
            'last_ping_status': request.GET.get('status'),
            'saved': request.GET.get('saved') == '1',
            'validated': request.GET.get('validated') == '1',
            'validate_result': request.session.pop('sitemap_validate', None),
            'flash': flash,
            'flash_kind': flash_kind,
        },
    )


@staff_member_required
def redirects_page(request):
    """List + create + edit + delete 301/302 Redirect rules.

    Mirrors the look of the bulk_meta page — one filter form, one
    list table, one inline create/edit form.
    """
    from plugins.installed.seo.models import Redirect

    if request.method == 'POST':
        action = (request.POST.get('action') or '').strip()
        if action == 'create':
            from_path = (request.POST.get('from_path') or '').strip()
            to_path = (request.POST.get('to_path') or '').strip()
            if from_path and to_path:
                Redirect.objects.update_or_create(
                    from_path=from_path,
                    defaults={
                        'to_path': to_path,
                        'status_code': int(request.POST.get('status_code') or 301),
                        'is_active': request.POST.get('is_active') == 'on',
                        'note': (request.POST.get('note') or '').strip()[:200],
                    },
                )
                messages.success(request, f'Saved redirect {from_path} → {to_path}.')
        elif action == 'edit':
            rid = (request.POST.get('id') or '').strip()
            if rid:
                Redirect.objects.filter(pk=rid).update(
                    from_path=(request.POST.get('from_path') or '').strip(),
                    to_path=(request.POST.get('to_path') or '').strip(),
                    status_code=int(request.POST.get('status_code') or 301),
                    is_active=request.POST.get('is_active') == 'on',
                    note=(request.POST.get('note') or '').strip()[:200],
                )
                messages.success(request, 'Redirect updated.')
        elif action == 'delete':
            rid = (request.POST.get('id') or '').strip()
            if rid:
                Redirect.objects.filter(pk=rid).delete()
                messages.success(request, 'Redirect deleted.')
        return redirect('seo_dashboard:redirects')

    edit_id = (request.GET.get('edit') or '').strip()
    rows = list(Redirect.objects.all().order_by('from_path'))
    edit_row = None
    if edit_id:
        edit_row = next((r for r in rows if str(r.pk) == edit_id), None)
    return render(
        request,
        'seo/redirects.html',
        {
            'rows': rows,
            'edit_row': edit_row,
            'active_nav': 'seo',
        },
    )


@staff_member_required
def seo_inspector(request):
    """Paste-a-slug, see-everything inspector for a single Product /
    Category / Collection / Journal post.

    Pure read — never writes a SeoMeta row, never runs an audit, never
    pings IndexNow. The view assembles, for one URL, the exact strings
    a crawler / AI engine would see: rendered title + description,
    canonical URL, robots meta, JSON-LD payload, OG tags, sitemap
    presence, the latest stored audit score (if any), and any tracked
    keywords whose target_url matches.
    """
    import json as _json
    from urllib.parse import urlparse

    entity_type = (request.GET.get('type') or '').strip().lower()
    raw_slug = (request.GET.get('slug') or '').strip()
    # Accept a full path in ?slug= ('/products/foo/') so the 404 log row
    # action can hand off the path as-is.
    slug = raw_slug
    if '/' in slug:
        parsed = urlparse(slug)
        parts = [p for p in (parsed.path or slug).split('/') if p]
        if parts:
            head = parts[0].lower()
            type_map = {
                'products': 'product',
                'category': 'category',
                'collection': 'collection',
                'journal': 'journal',
            }
            if head in type_map and len(parts) >= 2:
                if not entity_type:
                    entity_type = type_map[head]
                slug = parts[1]
            else:
                slug = parts[-1]

    ctx = {
        'active_nav': 'seo',
        'entity_type': entity_type,
        'slug': slug,
        'raw_slug': raw_slug,
        'type_choices': [
            ('product', 'Product'),
            ('category', 'Category'),
            ('collection', 'Collection'),
            ('journal', 'Journal post'),
        ],
        'entity': None,
        'not_found': False,
    }

    if not entity_type or not slug:
        return render(request, 'seo/inspector.html', ctx)

    # Resolve the entity. Catalog / CMS plugins are optional — fall
    # through to not_found on import error so the template renders.
    entity = None
    resolved_type = entity_type
    try:
        if entity_type == 'product':
            from plugins.installed.catalog.models import Product

            entity = Product.objects.filter(slug=slug).first()
        elif entity_type == 'category':
            from plugins.installed.catalog.models import Category

            entity = Category.objects.filter(slug=slug).first()
        elif entity_type == 'collection':
            from plugins.installed.catalog.models import Collection

            entity = Collection.objects.filter(slug=slug).first()
        elif entity_type == 'journal':
            from plugins.installed.cms.models import Page

            entity = Page.objects.filter(slug=slug, metadata__category='journal').first()
    except Exception:  # noqa: BLE001 — plugin import or DB hiccup
        entity = None

    if entity is None:
        ctx['not_found'] = True
        return render(request, 'seo/inspector.html', ctx)

    # Path + canonical URL.
    from plugins.installed.seo.services import (
        _site_base_url,
        iter_sitemap_entries,
        resolve_meta,
    )

    path_map = {
        'product': f'/products/{slug}/',
        'category': f'/category/{slug}/',
        'collection': f'/collection/{slug}/',
        'journal': f'/journal/{slug}/',
    }
    path = path_map.get(resolved_type, '')
    base = _site_base_url().rstrip('/')
    canonical_url = f'{base}{path}'

    # Title / description fallback chain. Mirrors resolve_meta() priority:
    # SeoMeta override → native model meta_title / meta_description →
    # template-style fallback (object name).
    fallback_title = getattr(entity, 'name', None) or getattr(entity, 'title', '') or ''
    fallback_desc = (
        getattr(entity, 'short_description', '')
        or getattr(entity, 'description', '')
        or getattr(entity, 'excerpt', '')
        or ''
    )
    resolved = resolve_meta(
        obj=entity,
        fallback_title=fallback_title,
        fallback_description=fallback_desc[:300] if fallback_desc else '',
        canonical_url=canonical_url,
    )

    # JSON-LD: pick the right generator by entity type.
    jsonld_payload: dict = {}
    try:
        if resolved_type == 'product':
            from plugins.installed.seo.services import product_jsonld

            jsonld_payload = product_jsonld(entity, base_url=base) or {}
        elif resolved_type in ('category', 'collection'):
            from plugins.installed.seo.services import collection_page_jsonld

            jsonld_payload = collection_page_jsonld(
                name=fallback_title,
                url=canonical_url,
                description=fallback_desc or '',
                items=[],
            )
        elif resolved_type == 'journal':
            from plugins.installed.seo.services import article_jsonld

            jsonld_payload = article_jsonld(
                headline=fallback_title,
                body=(getattr(entity, 'body', '') or fallback_desc or ''),
                url=canonical_url,
                author=str(getattr(entity, 'author', '') or ''),
                published_at=getattr(entity, 'publish_at', None),
                updated_at=getattr(entity, 'updated_at', None),
            )
    except Exception:  # noqa: BLE001 — never let JSON-LD failure hide the page
        jsonld_payload = {}
    jsonld_text = (
        _json.dumps(jsonld_payload, indent=2, ensure_ascii=False) if jsonld_payload else ''
    )

    # Sitemap presence — scan iter_sitemap_entries up to the configured cap.
    in_sitemap = False
    try:
        from plugins.installed.seo.services import _sitemap_max_urls

        cap = _sitemap_max_urls()
    except Exception:  # noqa: BLE001
        cap = 50000
    try:
        for i, entry in enumerate(iter_sitemap_entries()):
            if i >= cap:
                break
            loc = (entry.get('loc') or '').rstrip('/')
            if loc == canonical_url.rstrip('/'):
                in_sitemap = True
                break
    except Exception:  # noqa: BLE001
        pass

    # Latest audit row.
    audit = None
    try:
        from django.contrib.contenttypes.models import ContentType
        from plugins.installed.seo.models import SeoAuditResult

        ct = ContentType.objects.get_for_model(type(entity))
        audit = SeoAuditResult.objects.filter(content_type=ct, object_id=str(entity.pk)).first()
    except Exception:  # noqa: BLE001
        audit = None

    # AEO / GEO answer-readiness score — products only (the scorer is
    # product-shaped). Surfaces the per-signal checklist in the inspector
    # so the merchant sees exactly what makes the page citable by AI.
    aeo = None
    if resolved_type == 'product':
        try:
            from plugins.installed.seo.services.audit import score_aeo

            aeo = score_aeo(entity)
        except Exception:  # noqa: BLE001 — never let the scorer hide the page
            aeo = None

    # Tracked keywords pointing at this canonical URL.
    matching_keywords = []
    try:
        from plugins.installed.seo.models import TrackedKeyword

        matching_keywords = list(
            TrackedKeyword.objects.filter(target_url=canonical_url).order_by('keyword')
        )
        if not matching_keywords:
            # Some merchants store target_url as a path. Also match those.
            matching_keywords = list(
                TrackedKeyword.objects.filter(target_url=path).order_by('keyword')
            )
    except Exception:  # noqa: BLE001
        matching_keywords = []

    og_tags = [
        ('og:title', resolved.og_title or resolved.title),
        ('og:description', resolved.og_description or resolved.description),
        ('og:url', canonical_url),
        ('og:type', resolved.og_type),
        ('og:image', resolved.og_image),
        ('twitter:card', resolved.twitter_card),
    ]

    ctx.update(
        {
            'entity': entity,
            'entity_type': resolved_type,
            'entity_label': type(entity).__name__,
            'path': path,
            'canonical_url': canonical_url,
            'resolved_title': resolved.title or fallback_title,
            'resolved_description': resolved.description or fallback_desc[:300],
            'resolved_robots': resolved.robots or 'index, follow',
            'in_sitemap': in_sitemap,
            'jsonld_text': jsonld_text,
            'og_tags': og_tags,
            'audit': audit,
            'aeo': aeo,
            'matching_keywords': matching_keywords,
        }
    )
    return render(request, 'seo/inspector.html', ctx)


@staff_member_required
def not_found_dismiss(request, pk):
    """Mark a NotFoundLog row resolved without creating a redirect.

    Useful when the merchant knows the path is spam / a probe / a
    known-deprecated URL that shouldn't pollute the queue.
    """
    from plugins.installed.seo.models import NotFoundLog

    if request.method == 'POST':
        log = get_object_or_404(NotFoundLog, pk=pk)
        log.is_resolved = True
        log.save(update_fields=['is_resolved'])
        messages.success(request, 'Marked 404 as resolved.')
    return redirect('seo_dashboard:not_found')


# --- Visual structured-data (schema.org) editor ---------------------------
# A per-object editor: pick a schema.org @type from a friendly list and fill
# labeled fields (no JSON). Entries are stored on SeoMeta.schema_blocks and
# built into <script type="application/ld+json"> at render time (see
# services/meta.py:_visual_schema_blocks). Reached from the product/page forms.


@staff_member_required
def schema_index(request: HttpRequest) -> HttpResponse:
    from django.urls import reverse

    from plugins.installed.seo.models import SeoMeta

    rows = []
    for meta in SeoMeta.objects.exclude(schema_blocks=[]).select_related('content_type')[:200]:
        if not meta.schema_blocks:
            continue
        ct = meta.content_type
        try:
            obj = ct.get_object_for_this_type(pk=meta.object_id)
        except Exception:
            obj = None
        types = sorted({e.get('type', '') for e in meta.schema_blocks if isinstance(e, dict)})
        rows.append(
            {
                'label': str(obj) if obj else f'{ct.model} #{meta.object_id}',
                'count': len(meta.schema_blocks),
                'types': ', '.join(t for t in types if t),
                'edit_url': reverse(
                    'seo_dashboard:schema_editor',
                    args=[ct.app_label, ct.model, meta.object_id],
                ),
            }
        )
    return render(
        request,
        'seo/schema_index.html',
        {
            'rows': rows,
            'active_nav': 'seo',
            'breadcrumb_trail': [
                {'label': 'Dashboard', 'url': '/dashboard/'},
                {'label': 'SEO', 'url': '/dashboard/seo/'},
                {'label': 'Structured data'},
            ],
        },
    )


@staff_member_required
def schema_editor(request: HttpRequest, app_label: str, model: str, pk: str) -> HttpResponse:
    from django.contrib.contenttypes.models import ContentType

    from morpheus.views import Http404
    from plugins.installed.seo.models import SeoMeta
    from plugins.installed.seo.schema_types import build_block, registry_json

    ct = ContentType.objects.filter(app_label=app_label, model=model).first()
    if ct is None:
        raise Http404('Unknown content type.')

    try:
        obj = ct.get_object_for_this_type(pk=pk)
    except Exception:
        obj = None

    meta = SeoMeta.objects.filter(content_type=ct, object_id=str(pk)).first()

    if request.method == 'POST':
        try:
            entries = json.loads(request.POST.get('blocks_json') or '[]')
        except (ValueError, TypeError):
            entries = []
        clean = [
            {'type': e.get('type', ''), 'data': e.get('data') or {}}
            for e in entries
            if isinstance(e, dict) and build_block(e.get('type', ''), e.get('data') or {})
        ]
        meta, _ = SeoMeta.objects.get_or_create(content_type=ct, object_id=str(pk))
        meta.schema_blocks = clean
        meta.save()
        messages.success(request, f'Structured data saved ({len(clean)} block(s)).')
        return redirect('seo_dashboard:schema_editor', app_label=app_label, model=model, pk=str(pk))

    try:
        object_url = obj.get_absolute_url() if (obj and hasattr(obj, 'get_absolute_url')) else ''
    except Exception:
        object_url = ''

    return render(
        request,
        'seo/schema_editor.html',
        {
            'app_label': app_label,
            'model': model,
            'pk': str(pk),
            'object_label': str(obj) if obj else f'{model} #{pk}',
            'object_url': object_url,
            # Passed as Python objects → rendered with |json_script, which escapes
            # </script> in user answer text. The editor JS JSON.parses them.
            'schema_types': registry_json(),
            'existing_blocks': meta.schema_blocks if meta else [],
            'active_nav': 'seo',
            'breadcrumb_trail': [
                {'label': 'Dashboard', 'url': '/dashboard/'},
                {'label': 'SEO', 'url': '/dashboard/seo/'},
                {'label': 'Structured data', 'url': '/dashboard/seo/schema/'},
                {'label': (str(obj) if obj else model)[:40]},
            ],
        },
    )
