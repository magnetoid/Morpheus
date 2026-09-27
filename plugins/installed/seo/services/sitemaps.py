"""Sitemap iteration + XML rendering.

The five XML sitemaps + the iteration helper that drives the main one
all live here. Crawler-facing files that aren't sitemaps (robots.txt,
llms.txt, PWA manifest) live in ``crawler_files`` instead.
"""
# Legacy sitemap module: lazy (in-function) imports + fail-soft builders are the
# established pattern here.
# ruff: noqa: PLC0415, S110, SIM105, SIM113, PLR1730, UP035, PLR0912

from __future__ import annotations

from datetime import timedelta
from typing import Iterable
from urllib.parse import urljoin

from django.utils.html import escape

from ._helpers import _seo_plugin, _site_base_url, logger, site_settings


def _iter_author_entries(base: str) -> Iterable[dict]:
    """Authors are derived from ``Metafield`` rows
    (``namespace='book'``, ``key='author'``). ``author_detail`` enumerates
    by ``slugify(name)`` — match the same shape here so the sitemap URLs
    actually resolve."""
    try:
        from django.utils.text import slugify

        from plugins.installed.book_product.compat import distinct_values

        names = distinct_values('author')  # model-first, legacy book.* fallback
        seen: set[str] = set()
        for name in names:
            slug = slugify(name)
            if not slug or slug in seen:
                continue
            seen.add(slug)
            yield {
                'loc': urljoin(base, f'/author/{slug}/'),
                'changefreq': 'weekly',
                'priority': '0.5',
            }
    except Exception as e:  # noqa: BLE001 — metafields plugin optional
        logger.debug('seo: sitemap authors skipped: %s', e)


def _iter_webstory_entries(base: str) -> Iterable[dict]:
    """One ``/story/<slug>/`` URL per published WebStory. Stories are
    standalone + self-canonical (no ``rel='amphtml'`` pairing from the PDP),
    so listing their URLs in the main sitemap is what gets them discovered and
    into Google's Web Stories surface."""
    try:
        from plugins.installed.webstories.models import WebStory

        rows = (
            WebStory.objects.filter(is_published=True)
            .select_related('product')
            .only('updated_at', 'product__slug', 'product__status')
        )
        for s in rows:
            if getattr(s.product, 'status', '') != 'active':
                continue
            yield {
                'loc': urljoin(base, f'/story/{s.product.slug}/'),
                'lastmod': s.updated_at.isoformat() if s.updated_at else '',
                'changefreq': 'weekly',
                'priority': '0.5',
            }
    except Exception as e:  # noqa: BLE001 — webstories plugin optional
        logger.debug('seo: sitemap webstories skipped: %s', e)


def _iter_book_facet_entries(base: str) -> Iterable[dict]:
    """Book-taxonomy landing pages owned by the book_product plugin:
    ``/publisher/<slug>/``, ``/series/<slug>/``, ``/imprint/<slug>/`` (matched by
    ``slugify`` of the stored value) and ``/format/<value>/``,
    ``/language/<value>/`` (matched by the raw enum value). Only taxonomies with
    at least one *active* product are emitted — the facet views 404 on an empty
    set, so listing an empty one would put a dead URL in the sitemap."""
    try:
        from django.utils.text import slugify

        from plugins.installed.book_product.models import BookProduct

        active = BookProduct.objects.filter(product__status='active')
        for prefix, field in (
            ('publisher', 'publisher'),
            ('series', 'series'),
            ('imprint', 'imprint'),
        ):
            seen: set[str] = set()
            for value in active.exclude(**{field: ''}).values_list(field, flat=True):
                slug = slugify(value or '')
                if not slug or slug in seen:
                    continue
                seen.add(slug)
                yield {
                    'loc': urljoin(base, f'/{prefix}/{slug}/'),
                    'changefreq': 'weekly',
                    'priority': '0.5',
                }
        for prefix, field in (('format', 'print_type'), ('language', 'language')):
            seen = set()
            for raw in active.exclude(**{field: ''}).values_list(field, flat=True):
                value = (raw or '').strip()
                if not value or value in seen:
                    continue
                seen.add(value)
                yield {
                    'loc': urljoin(base, f'/{prefix}/{value}/'),
                    'changefreq': 'weekly',
                    'priority': '0.5',
                }
        # Curated taxonomies (Genre, Topic) — only those with ≥1 active book
        # (the index/detail views 404 on an empty set, so an empty one is dead).
        from plugins.installed.book_product.models import Genre, Topic

        for prefix, model in (('genre', Genre), ('topic', Topic)):
            for obj in model.objects.filter(is_active=True):
                if obj.books.filter(product__status='active').exists():
                    yield {
                        'loc': urljoin(base, f'/{prefix}/{obj.slug}/'),
                        'changefreq': 'weekly',
                        'priority': '0.6',
                    }
    except Exception as e:  # noqa: BLE001 — book_product plugin optional
        logger.debug('seo: sitemap book facets skipped: %s', e)


def _iter_cms_page_entries(base: str) -> Iterable[dict]:
    """Every *published* CMS page, so any page a merchant adds shows up in the
    sitemap automatically. Journal posts live at ``/journal/<slug>/``; every
    other page renders through the CMS resolver at ``/p/<slug>/``. Scheduled
    (future ``publish_at``) pages are held back until they go live."""
    try:
        from django.utils import timezone

        from plugins.installed.cms.models import Page

        now = timezone.now()
        for p in Page.objects.filter(state='published').only(
            'slug', 'updated_at', 'publish_at', 'metadata'
        ):
            if p.publish_at and p.publish_at > now:
                continue
            is_journal = (p.metadata or {}).get('category') == 'journal'
            path = f'/journal/{p.slug}/' if is_journal else f'/p/{p.slug}/'
            yield {
                'loc': urljoin(base, path),
                'lastmod': p.updated_at.isoformat() if p.updated_at else '',
                'changefreq': 'monthly',
                'priority': '0.5',
            }
    except Exception as e:  # noqa: BLE001 — cms plugin optional
        logger.debug('seo: sitemap cms pages skipped: %s', e)


def _seo_overrides(model) -> dict:
    """`{object_id: (sitemap_include, robots)}` for one model, in ONE query.

    A sitemap that lists a noindex URL asks Google to crawl a page it is then
    told to drop — wasted crawl budget, and a "Discovered but not indexed"
    entry that looks like a problem. The merchant's own per-page choice
    (`SeoMeta.sitemap_include`) overrides both ways.
    """
    try:
        from django.contrib.contenttypes.models import ContentType

        from plugins.installed.seo.models import SeoMeta

        ct = ContentType.objects.get_for_model(model)
        return {
            str(object_id): (include, robots or '')
            for object_id, include, robots in SeoMeta.objects.filter(content_type=ct).values_list(
                'object_id', 'sitemap_include', 'robots'
            )
        }
    except Exception as e:  # noqa: BLE001 — an unmigrated DB lists everything
        logger.debug('seo: sitemap overrides unavailable: %s', e)
        return {}


def _in_sitemap(overrides: dict, obj) -> bool:
    """Whether this object's URL belongs in the sitemap."""
    include, robots = overrides.get(str(obj.pk), (None, ''))
    if include is not None:
        return bool(include)
    return 'noindex' not in (robots or '').lower()


def iter_sitemap_entries() -> Iterable[dict]:
    """Yield entries that should appear in the sitemap. Pulls from:

    1. Active products (catalog)
    2. Active categories (catalog)
    3. Active collections (catalog)
    4. Active vendors (catalog)
    5. Authors — distinct values from book/author metafields
    6. Journal entries (cms)
    7. Manually-curated SitemapEntry rows
    """
    base = _site_base_url()

    yield {'loc': base, 'changefreq': 'daily', 'priority': '1.0'}

    try:
        from plugins.installed.catalog.models import Category, Collection, Product, Vendor

        product_seo = _seo_overrides(Product)
        for p in Product.objects.filter(status='active').only('slug', 'updated_at'):
            if not _in_sitemap(product_seo, p):
                continue
            yield {
                'loc': urljoin(base, f'/products/{p.slug}/'),
                'lastmod': p.updated_at.isoformat() if p.updated_at else '',
                'changefreq': 'weekly',
                'priority': '0.8',
                'md_alternate': urljoin(base, f'/md/products/{p.slug}'),
            }
        category_seo = _seo_overrides(Category)
        for c in Category.objects.filter(is_active=True).only('slug', 'updated_at'):
            if not _in_sitemap(category_seo, c):
                continue
            yield {
                'loc': urljoin(base, f'/category/{c.slug}/'),
                'lastmod': c.updated_at.isoformat() if c.updated_at else '',
                'changefreq': 'weekly',
                'priority': '0.6',
            }
        collection_seo = _seo_overrides(Collection)
        for col in Collection.objects.filter(is_active=True).only('slug', 'updated_at'):
            if not _in_sitemap(collection_seo, col):
                continue
            yield {
                'loc': urljoin(base, f'/collection/{col.slug}/'),
                'lastmod': col.updated_at.isoformat() if col.updated_at else '',
                'changefreq': 'weekly',
                'priority': '0.6',
            }
        for v in Vendor.objects.filter(is_active=True).only('slug', 'created_at'):
            yield {
                'loc': urljoin(base, f'/vendor/{v.slug}/'),
                'lastmod': v.created_at.isoformat() if v.created_at else '',
                'changefreq': 'weekly',
                'priority': '0.6',
            }
    except Exception as e:  # noqa: BLE001 — catalog plugin is optional
        logger.debug('seo: sitemap catalog skipped: %s', e)

    yield from _iter_author_entries(base)
    yield from _iter_book_facet_entries(base)
    yield from _iter_webstory_entries(base)

    # Static editorial routes shipped by the storefront plugin. These don't
    # have model rows so they're hard-coded here; cheap and stable.
    # `/categories/` is deliberately NOT here: the book vertical replaces it
    # with `/genres/`, so on those stores it is a permanent redirect and a
    # sitemap must never invite a crawler to one. storefront contributes it
    # through SITEMAP_URLS when it actually serves the page
    # (`storefront/sitemap.py`) — the owner knows, seo cannot.
    for path in (
        '/products/',
        '/staff-picks/',
        '/vendors/',
        '/about/',
        '/contact/',
        '/journal/',
    ):
        yield {'loc': urljoin(base, path), 'changefreq': 'weekly', 'priority': '0.7'}
    # Policy pages — low priority, change rarely.
    for path in ('/shipping/', '/returns/'):
        yield {'loc': urljoin(base, path), 'changefreq': 'monthly', 'priority': '0.4'}

    # Every published CMS page (journal posts + standalone /p/<slug>/ pages),
    # so any page a merchant adds is picked up automatically.
    yield from _iter_cms_page_entries(base)

    try:
        from plugins.installed.seo.models import SitemapEntry

        for row in SitemapEntry.objects.filter(is_active=True):
            raw = (row.location or '').strip()
            if not raw:
                continue
            loc = raw if raw.startswith(('http://', 'https://')) else urljoin(base, raw)
            yield {
                'loc': loc,
                'lastmod': row.last_modified.isoformat() if row.last_modified else '',
                'changefreq': row.changefreq,
                'priority': str(row.priority),
            }
    except Exception as e:  # noqa: BLE001
        logger.debug('seo: manual sitemap entries skipped: %s', e)


def _normalize_contributed_entry(e: dict) -> dict:
    """SITEMAP_URLS subscribers may hand back raw ``date``/``datetime``
    lastmod values and numeric priorities (the filter's documented payload
    shape); the renderer below expects the same string-only shape
    ``iter_sitemap_entries()`` already yields. Native entries pass through
    unchanged (already strings)."""
    lastmod = e.get('lastmod')
    priority = e.get('priority')
    if hasattr(lastmod, 'isoformat') or isinstance(priority, (int, float)):
        e = dict(e)
        if hasattr(lastmod, 'isoformat'):
            e['lastmod'] = lastmod.isoformat()
        if isinstance(priority, (int, float)):
            e['priority'] = str(priority)
    return e


def _merged_sitemap_entries() -> list[dict]:
    """Native ``iter_sitemap_entries()`` output + anything folded in through
    the ``SITEMAP_URLS`` filter, deduped by ``loc`` — first entry wins, so a
    contributed URL can never shadow a native one. This is how an app whose
    routes seo knows nothing about (bookings, stays, a vertical's facets)
    reaches the sitemap without seo importing it."""
    from core.hooks import MorpheusEvents, hook_registry

    native = list(iter_sitemap_entries())
    # Which locs seo generated itself, so the dashboard can tell a contributed
    # route (a booking, a stay) from a hand-written SitemapEntry — they land in
    # the same "matches no native prefix" bucket otherwise.
    native_locs = {e.get('loc') for e in native if isinstance(e, dict)}
    entries = hook_registry.filter(MorpheusEvents.SITEMAP_URLS, native)
    seen: set[str] = set()
    merged: list[dict] = []
    for e in entries:
        # Fail-soft: a buggy subscriber handing back a non-dict (None, str, …)
        # must not 500 /sitemap.xml — skip it and keep rendering.
        if not isinstance(e, dict):
            logger.warning('seo: sitemap contribution skipped (non-dict entry): %r', e)
            continue
        loc = e.get('loc')
        if not loc or loc in seen:
            continue
        seen.add(loc)
        entry = _normalize_contributed_entry(e)
        if loc not in native_locs:
            entry['_contributed'] = True
        merged.append(entry)
    return merged


def sitemap_counts() -> dict:  # noqa: PLR0912 — flat per-source classifier; branches are clearer than a dispatch table
    """Aggregate every URL the sitemap serves into per-source counts +
    overall last-modified timestamps. Used by the Sitemap dashboard.

    Counts the MERGED corpus — native entries plus everything folded in
    through `SITEMAP_URLS`. It used to count `iter_sitemap_entries()` alone, so
    on any store whose catalogue lives in a contributing app the page reported
    a fraction of the real sitemap: the Montenegro marketplace's dashboard said
    59 URLs while `/sitemap.xml` served 343, hiding all 284 bookings, stays,
    places and events. A dashboard that under-reports by 6x is worse than one
    that shows nothing, because it looks like an answer.

    Returns a dict shaped:
        {
          'total': int,
          'product_count': int, 'category_count': int,
          'collection_count': int, 'journal_count': int,
          'static_count': int, 'manual_count': int,
          'last_modified': isoformat str | '',
        }
    """
    counts = {
        'total': 0,
        'product_count': 0,
        'category_count': 0,
        'collection_count': 0,
        'vendor_count': 0,
        'author_count': 0,
        'book_facet_count': 0,
        'page_count': 0,
        'journal_count': 0,
        'static_count': 0,
        'manual_count': 0,
        'contributed_count': 0,
        'last_modified': '',
        'truncated': False,
    }
    book_facet_prefixes = ('/publisher/', '/series/', '/imprint/', '/format/', '/language/')
    base = _site_base_url().rstrip('/')
    static_routes = (
        '/',
        '/products/',
        '/staff-picks/',
        '/categories/',
        '/vendors/',
        '/about/',
        '/contact/',
        '/journal/',
        '/shipping/',
        '/returns/',
    )
    cap = _sitemap_max_urls()
    latest = ''
    for e in _merged_sitemap_entries():
        counts['total'] += 1
        loc = e.get('loc', '')
        path = loc[len(base) :] if loc.startswith(base) else loc
        if path.startswith('/products/') and path.count('/') >= 3:
            counts['product_count'] += 1
        elif path.startswith('/category/'):
            counts['category_count'] += 1
        elif path.startswith('/collection/'):
            counts['collection_count'] += 1
        elif path.startswith('/vendor/'):
            counts['vendor_count'] += 1
        elif path.startswith('/author/'):
            counts['author_count'] += 1
        elif path.startswith(book_facet_prefixes):
            counts['book_facet_count'] += 1
        elif path.startswith('/journal/') and path != '/journal/':
            counts['journal_count'] += 1
        elif path.startswith('/p/'):
            counts['page_count'] += 1
        elif path in static_routes:
            counts['static_count'] += 1
        elif e.get('_contributed'):
            counts['contributed_count'] += 1
        else:
            counts['manual_count'] += 1
        lm = e.get('lastmod') or ''
        if lm > latest:
            latest = lm
    counts['last_modified'] = latest
    if counts['total'] > cap:
        counts['truncated'] = True
    return counts


def regenerate_sitemap(triggered_by: str = 'dashboard') -> dict:
    """Re-publish the sitemap. It's rendered live on every request, so
    'regenerate' means: recount entries, purge the CDN's cached copies of the
    sitemap URLs (so the edge re-fetches the fresh document), and ping IndexNow
    so crawlers re-pull. Every step is best-effort — a missing Cloudflare/
    IndexNow config degrades gracefully. Returns a summary dict for the caller
    (dashboard flash, management command, Linda tool)."""
    from .indexnow import ping_indexnow

    base = _site_base_url().rstrip('/')
    paths = ('/sitemap.xml', '/sitemap-index.xml', '/sitemap-images.xml', '/sitemap-news.xml')
    result = {'counts': {}, 'purged': False, 'pinged': False, 'ping_status': ''}
    try:
        result['counts'] = sitemap_counts()
    except Exception as e:  # noqa: BLE001
        logger.warning('seo.regenerate_sitemap: counts failed: %s', e)
    # Fire, don't import: this used to reach into the cloudflare app's models
    # and services directly, which made seo depend on an optional sibling for a
    # capability it only wants to *request*. Whoever owns the edge subscribes.
    try:
        from morpheus.core import MorpheusEvents, hook_registry

        # A purge is REQUESTED, not counted: seo no longer knows how many CDN
        # zones exist, and reporting a zone count it cannot see would be a
        # number the merchant has no way to check.
        hook_registry.fire(
            MorpheusEvents.EDGE_PURGE_URLS,
            urls=list(paths),
            reason=triggered_by or 'sitemap-regenerate',
        )
        result['purged'] = True
    except Exception as e:  # noqa: BLE001 — a CDN must never fail a regeneration
        logger.debug('seo.regenerate_sitemap: edge purge skipped: %s', e)
    try:
        ping = ping_indexnow([f'{base}/sitemap-index.xml'])
        result['pinged'] = bool(ping.get('ok'))
        result['ping_status'] = str(ping.get('status') or ping.get('error') or '')
    except Exception as e:  # noqa: BLE001
        logger.warning('seo.regenerate_sitemap: ping failed: %s', e)
    return result


def _sitemap_max_urls() -> int:
    """Read the configured per-file cap; clamp to Google's hard limit
    of 50,000 entries (https://www.sitemaps.org/protocol.html)."""
    cap = 50000
    seo_plugin = _seo_plugin()
    if seo_plugin is not None:
        try:
            cap = int(seo_plugin.get_config_value('sitemap_max_urls_per_file', 50000) or 50000)
        except (TypeError, ValueError):
            cap = 50000
    return max(100, min(cap, 50000))


def render_sitemap_xml() -> str:
    """Render the primary /sitemap.xml. Capped at
    `sitemap_max_urls_per_file` so we don't emit a > 50 MB document
    that Google rejects. Overflow is silently truncated — a split
    sitemap index is a follow-up (Phase 2 of the SEO knob wiring).

    URLs come from ``_merged_sitemap_entries()`` — the native list plus
    whatever other apps fold in through the ``SITEMAP_URLS`` filter, so seo
    never has to import a sibling to know its routes exist."""
    cap = _sitemap_max_urls()
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
        'xmlns:xhtml="http://www.w3.org/1999/xhtml">',
    ]
    count = 0
    for e in _merged_sitemap_entries():
        if count >= cap:
            logger.warning('seo: sitemap truncated at %d entries (cap=%d)', count, cap)
            break
        parts.append('<url>')
        parts.append(f'<loc>{escape(e["loc"])}</loc>')
        if e.get('lastmod'):
            parts.append(f'<lastmod>{escape(e["lastmod"])}</lastmod>')
        if e.get('changefreq'):
            parts.append(f'<changefreq>{escape(e["changefreq"])}</changefreq>')
        if e.get('priority'):
            parts.append(f'<priority>{escape(e["priority"])}</priority>')
        if e.get('md_alternate'):
            parts.append(
                f'<xhtml:link rel="alternate" type="text/markdown" '
                f'href="{escape(e["md_alternate"])}"/>'
            )
        parts.append('</url>')
        count += 1
    parts.append('</urlset>')
    return ''.join(parts)


def render_sitemap_index_xml() -> str:
    """Sitemap index — points at every sub-sitemap. Crawlers discover
    sub-sitemaps from here without hitting the main sitemap.xml
    against the 50k-URL limit.

    Only lists a sub-sitemap the store actually serves: image/news are
    merchant-configurable (`image_sitemap_enabled` default on,
    `news_sitemap_enabled` default off — same defaults `views.py` enforces
    when serving them) and a listed-but-404 child wastes crawl budget on a
    dead fetch every time.
    """
    from django.utils import timezone

    base = _site_base_url().rstrip('/')
    now = timezone.now().replace(microsecond=0).isoformat()
    children = [f'{base}/sitemap.xml']
    seo_plugin = _seo_plugin()
    image_enabled, news_enabled = True, False
    if seo_plugin is not None:
        try:
            image_enabled = bool(seo_plugin.get_config_value('image_sitemap_enabled', True))
        except Exception:  # noqa: BLE001
            image_enabled = True
        try:
            news_enabled = bool(seo_plugin.get_config_value('news_sitemap_enabled', False))
        except Exception:  # noqa: BLE001
            news_enabled = False
    if image_enabled:
        children.append(f'{base}/sitemap-images.xml')
    if news_enabled:
        children.append(f'{base}/sitemap-news.xml')
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for child in children:
        parts.append('<sitemap>')
        parts.append(f'<loc>{escape(child)}</loc>')
        parts.append(f'<lastmod>{escape(now)}</lastmod>')
        parts.append('</sitemap>')
    parts.append('</sitemapindex>')
    return ''.join(parts)


def render_news_sitemap_xml() -> str:
    """News sitemap for journal posts.

    Google News strictly wants entries from the last 48 h, but most
    indie-publisher journals post weekly or less — an empty news
    sitemap is technically valid but useless for AI-citation
    discovery. The recency window is therefore configurable
    (``news_sitemap_max_age_hours`` in the seo plugin config;
    default 168 = 7 days), and we read journal entries directly from
    the cms.Page table where they actually live (``metadata.category =
    'journal'``).
    """
    from django.utils import timezone

    base = _site_base_url().rstrip('/')
    max_age_hours = 168  # 7 days default
    seo_plugin = _seo_plugin()
    if seo_plugin is not None:
        try:
            max_age_hours = int(
                seo_plugin.get_config_value('news_sitemap_max_age_hours', 168) or 168
            )
        except (TypeError, ValueError):
            pass
    cutoff = timezone.now() - timedelta(hours=max_age_hours)

    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
        'xmlns:news="http://www.google.com/schemas/sitemap-news/0.9">',
    ]
    try:
        from plugins.installed.cms.models import Page
    except Exception as exc:  # noqa: BLE001 — cms plugin not installed
        logger.debug('seo.news_sitemap: cms.Page unavailable: %s', exc)
        parts.append('</urlset>')
        return ''.join(parts)

    s = site_settings()
    pub_name = s.organization_name or 'Morpheus'
    qs = (
        Page.objects.filter(state='published', metadata__category='journal')
        .exclude(publish_at__gt=timezone.now())
        .filter(publish_at__gte=cutoff)
        .order_by('-publish_at')[:1000]
    )
    for post in qs:
        pub_at = post.publish_at or post.updated_at or post.created_at
        if pub_at is None:
            continue
        url = f'{base}/journal/{post.slug}/'
        pub = pub_at.replace(microsecond=0).isoformat()
        parts.append('<url>')
        parts.append(f'<loc>{escape(url)}</loc>')
        parts.append('<news:news>')
        parts.append('<news:publication>')
        parts.append(f'<news:name>{escape(pub_name)}</news:name>')
        parts.append('<news:language>en</news:language>')
        parts.append('</news:publication>')
        parts.append(f'<news:publication_date>{escape(pub)}</news:publication_date>')
        parts.append(f'<news:title>{escape(post.title)}</news:title>')
        parts.append('</news:news>')
        parts.append('</url>')
    parts.append('</urlset>')
    return ''.join(parts)


def render_image_sitemap_xml() -> str:
    """Image-only sitemap. Lists every product's primary image with its
    caption/alt so AI image-search engines (Google AI Overviews, Bing
    image grounding) can discover them.

    Spec: https://www.sitemaps.org/schemas/sitemap-image/1.1/sitemap-image.xsd
    """
    base = _site_base_url().rstrip('/')
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
        'xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">',
    ]
    try:
        from plugins.installed.catalog.models import Product

        cap = _sitemap_max_urls()
        qs = Product.objects.filter(status='active')
        total = qs.count()
        if total > cap:
            logger.warning('seo: image sitemap truncated at %d entries', cap)
        for p in qs.prefetch_related('images')[:cap]:
            page_url = f'{base}/products/{p.slug}/'
            imgs = list(p.images.all())
            if not imgs:
                continue
            parts.append('<url>')
            parts.append(f'<loc>{escape(page_url)}</loc>')
            for img in imgs[:6]:
                src = getattr(img.image, 'url', None) if getattr(img, 'image', None) else None
                if not src:
                    continue
                if not src.startswith('http'):
                    src = base + src
                # Only <image:loc> is still meaningful — Google deprecated
                # <image:caption>/<image:title>/<image:geo_location>/<image:license>
                # (they're ignored now), so we emit just the location.
                parts.append('<image:image>')
                parts.append(f'<image:loc>{escape(src)}</image:loc>')
                parts.append('</image:image>')
            parts.append('</url>')
    except Exception:  # noqa: BLE001
        pass
    parts.append('</urlset>')
    return ''.join(parts)


def render_opensearch_xml() -> str:
    """OpenSearch description — installs the site as a Chrome tab-to-
    search engine (Edge, Brave). Lightweight discoverability win.
    """
    base = _site_base_url().rstrip('/')
    s = site_settings()
    short = (s.organization_name or 'dot books')[:16]
    desc = (s.llms_txt_intro or short)[:160]
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<OpenSearchDescription xmlns="http://a9.com/-/spec/opensearch/1.1/">'
        f'<ShortName>{escape(short)}</ShortName>'
        f'<Description>{escape(desc)}</Description>'
        '<InputEncoding>UTF-8</InputEncoding>'
        f'<Image width="16" height="16" type="image/x-icon">{escape(base)}/favicon.ico</Image>'
        f'<Url type="text/html" method="get" template="{escape(base)}/products/?q={{searchTerms}}"/>'
        '</OpenSearchDescription>'
    )
