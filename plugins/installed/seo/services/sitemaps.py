"""Sitemap iteration + XML rendering.

The five XML sitemaps + the iteration helper that drives the main one
all live here. Crawler-facing files that aren't sitemaps (robots.txt,
llms.txt, PWA manifest) live in ``crawler_files`` instead.
"""
from __future__ import annotations

from datetime import timedelta
from typing import Iterable
from urllib.parse import urljoin

from django.utils.html import escape

from ._helpers import _seo_plugin, _site_base_url, logger, site_settings


def iter_sitemap_entries() -> Iterable[dict]:
    """Yield entries that should appear in the sitemap. Pulls from:

      1. Active products (catalog)
      2. Active categories (catalog)
      3. Active collections (catalog)
      4. Journal entries (cms)
      5. Manually-curated SitemapEntry rows
    """
    base = _site_base_url()

    yield {'loc': base, 'changefreq': 'daily', 'priority': '1.0'}

    try:
        from plugins.installed.catalog.models import Category, Collection, Product
        for p in Product.objects.filter(status='active').only('slug', 'updated_at'):
            yield {
                'loc': urljoin(base, f'/products/{p.slug}/'),
                'lastmod': p.updated_at.isoformat() if p.updated_at else '',
                'changefreq': 'weekly',
                'priority': '0.8',
            }
        for c in Category.objects.filter(is_active=True).only('slug', 'updated_at'):
            yield {
                'loc': urljoin(base, f'/category/{c.slug}/'),
                'lastmod': c.updated_at.isoformat() if c.updated_at else '',
                'changefreq': 'weekly',
                'priority': '0.6',
            }
        for col in Collection.objects.filter(is_active=True).only('slug', 'updated_at'):
            yield {
                'loc': urljoin(base, f'/c/{col.slug}/'),
                'lastmod': col.updated_at.isoformat() if col.updated_at else '',
                'changefreq': 'weekly',
                'priority': '0.6',
            }
    except Exception as e:  # noqa: BLE001 — catalog plugin is optional
        logger.debug('seo: sitemap catalog skipped: %s', e)

    # Static editorial routes shipped by the storefront plugin. These don't
    # have model rows so they're hard-coded here; cheap and stable.
    for path in ('/products/', '/staff-picks/', '/about/', '/contact/', '/journal/'):
        yield {'loc': urljoin(base, path), 'changefreq': 'weekly', 'priority': '0.7'}

    # Journal entries — pulled from cms.Page rows tagged metadata.category=='journal'.
    try:
        from plugins.installed.cms.models import Page
        for j in (Page.objects
                  .filter(state='published', metadata__category='journal')
                  .only('slug', 'updated_at')):
            yield {
                'loc': urljoin(base, f'/journal/{j.slug}/'),
                'lastmod': j.updated_at.isoformat() if j.updated_at else '',
                'changefreq': 'monthly',
                'priority': '0.5',
            }
    except Exception as e:  # noqa: BLE001 — cms plugin is optional
        logger.debug('seo: sitemap journal skipped: %s', e)

    try:
        from plugins.installed.seo.models import SitemapEntry
        for row in SitemapEntry.objects.filter(is_active=True):
            yield {
                'loc': row.location,
                'lastmod': row.last_modified.isoformat() if row.last_modified else '',
                'changefreq': row.changefreq,
                'priority': str(row.priority),
            }
    except Exception as e:  # noqa: BLE001
        logger.debug('seo: manual sitemap entries skipped: %s', e)


def sitemap_counts() -> dict:
    """Aggregate ``iter_sitemap_entries()`` into per-source counts +
    overall last-modified timestamps. Used by the Sitemap dashboard.

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
        'product_count': 0, 'category_count': 0, 'collection_count': 0,
        'journal_count': 0, 'static_count': 0, 'manual_count': 0,
        'last_modified': '',
    }
    base = _site_base_url().rstrip('/')
    latest = ''
    for e in iter_sitemap_entries():
        counts['total'] += 1
        loc = e.get('loc', '')
        path = loc[len(base):] if loc.startswith(base) else loc
        if path.startswith('/products/') and path.count('/') >= 3:
            counts['product_count'] += 1
        elif path.startswith('/category/'):
            counts['category_count'] += 1
        elif path.startswith('/c/'):
            counts['collection_count'] += 1
        elif path.startswith('/journal/') and path != '/journal/':
            counts['journal_count'] += 1
        elif path in ('/', '/products/', '/staff-picks/', '/about/',
                      '/contact/', '/journal/'):
            counts['static_count'] += 1
        else:
            counts['manual_count'] += 1
        lm = e.get('lastmod') or ''
        if lm > latest:
            latest = lm
    counts['last_modified'] = latest
    return counts


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
    sitemap index is a follow-up (Phase 2 of the SEO knob wiring)."""
    cap = _sitemap_max_urls()
    parts = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    count = 0
    for e in iter_sitemap_entries():
        if count >= cap:
            break
        parts.append('<url>')
        parts.append(f'<loc>{escape(e["loc"])}</loc>')
        if e.get('lastmod'):
            parts.append(f'<lastmod>{escape(e["lastmod"])}</lastmod>')
        if e.get('changefreq'):
            parts.append(f'<changefreq>{escape(e["changefreq"])}</changefreq>')
        if e.get('priority'):
            parts.append(f'<priority>{escape(e["priority"])}</priority>')
        parts.append('</url>')
        count += 1
    parts.append('</urlset>')
    return ''.join(parts)


def render_sitemap_index_xml() -> str:
    """Sitemap index — points at every sub-sitemap. Crawlers discover
    sub-sitemaps from here without hitting the main sitemap.xml
    against the 50k-URL limit.
    """
    from django.utils import timezone
    base = _site_base_url().rstrip('/')
    now = timezone.now().replace(microsecond=0).isoformat()
    children = [
        f'{base}/sitemap.xml',
        f'{base}/sitemap-images.xml',
        f'{base}/sitemap-news.xml',
    ]
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
            max_age_hours = int(seo_plugin.get_config_value('news_sitemap_max_age_hours', 168) or 168)
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
    qs = (Page.objects
          .filter(state='published', metadata__category='journal')
          .exclude(publish_at__gt=timezone.now())
          .filter(publish_at__gte=cutoff)
          .order_by('-publish_at')[:1000])
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
        for p in Product.objects.filter(status='active').prefetch_related('images')[:5000]:
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
                parts.append('<image:image>')
                parts.append(f'<image:loc>{escape(src)}</image:loc>')
                caption = (getattr(img, 'alt_text', '') or p.name or '').strip()
                if caption:
                    parts.append(f'<image:caption>{escape(caption[:200])}</image:caption>')
                parts.append(f'<image:title>{escape(p.name[:80])}</image:title>')
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
