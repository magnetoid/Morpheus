"""
SEO service layer: meta resolution, JSON-LD generation, sitemap building,
and AI-driven autofill.
"""
from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Iterable
from urllib.parse import urljoin

from django.conf import settings
from django.utils.html import escape

logger = logging.getLogger('morpheus.seo')

# Re-export to make `SeoMeta` reachable from `audit_product` below
# without forcing a per-call import (services.py already returns SeoMeta
# rows in `resolve_meta`; this is the same model).
from plugins.installed.seo.models import SeoMeta  # noqa: E402, F401


@dataclass(slots=True)
class ResolvedMeta:
    """Concrete, fallback-resolved meta values ready for rendering."""
    title: str = ''
    description: str = ''
    og_title: str = ''
    og_description: str = ''
    og_image: str = ''
    og_type: str = 'website'
    twitter_card: str = 'summary_large_image'
    canonical_url: str = ''
    robots: str = 'index, follow'
    keywords: str = ''
    structured_data: dict = None  # type: ignore[assignment]

    def to_html(self) -> str:
        """Render the meta tags as an HTML fragment for the <head>."""
        parts: list[str] = []
        if self.title:
            parts.append(f'<title>{escape(self.title)}</title>')
        if self.description:
            parts.append(f'<meta name="description" content="{escape(self.description)}">')
        if self.keywords:
            parts.append(f'<meta name="keywords" content="{escape(self.keywords)}">')
        if self.robots:
            parts.append(f'<meta name="robots" content="{escape(self.robots)}">')
        if self.canonical_url:
            parts.append(f'<link rel="canonical" href="{escape(self.canonical_url)}">')

        og_title = self.og_title or self.title
        og_desc = self.og_description or self.description
        if og_title:
            parts.append(f'<meta property="og:title" content="{escape(og_title)}">')
        if og_desc:
            parts.append(f'<meta property="og:description" content="{escape(og_desc)}">')
        parts.append(f'<meta property="og:type" content="{escape(self.og_type)}">')
        if self.og_image:
            parts.append(f'<meta property="og:image" content="{escape(self.og_image)}">')

        parts.append(f'<meta name="twitter:card" content="{escape(self.twitter_card)}">')
        if og_title:
            parts.append(f'<meta name="twitter:title" content="{escape(og_title)}">')
        if og_desc:
            parts.append(f'<meta name="twitter:description" content="{escape(og_desc)}">')
        if self.og_image:
            parts.append(f'<meta name="twitter:image" content="{escape(self.og_image)}">')

        if self.structured_data:
            parts.append(
                '<script type="application/ld+json">'
                + json.dumps(self.structured_data, separators=(',', ':'))
                + '</script>'
            )
        return '\n'.join(parts)


def resolve_meta(
    *,
    obj: Any | None = None,
    fallback_title: str = '',
    fallback_description: str = '',
    fallback_image: str = '',
    canonical_url: str = '',
    og_type: str = 'website',
) -> ResolvedMeta:
    """Merge per-object SeoMeta with fallback values into a ResolvedMeta."""
    from plugins.installed.seo.models import SeoMeta

    meta = SeoMeta.for_obj(obj) if obj is not None else None

    title = (meta.title if meta and meta.title else fallback_title).strip()
    description = (meta.description if meta and meta.description else fallback_description).strip()
    og_image = (meta.og_image if meta and meta.og_image else fallback_image).strip()
    canonical = (meta.canonical_url if meta and meta.canonical_url else canonical_url).strip()
    robots = meta.robots if meta else 'index, follow'
    keywords = meta.keywords if meta else ''
    twitter_card = meta.twitter_card if meta else 'summary_large_image'
    type_ = (meta.og_type if meta and meta.og_type else og_type)

    structured = _structured_data_for(obj, title=title, description=description, image=og_image)
    if meta and meta.structured_data:
        structured = {**structured, **meta.structured_data}

    return ResolvedMeta(
        title=title,
        description=description,
        og_title=meta.og_title if meta else '',
        og_description=meta.og_description if meta else '',
        og_image=og_image,
        og_type=type_,
        twitter_card=twitter_card,
        canonical_url=canonical,
        robots=robots,
        keywords=keywords,
        structured_data=structured,
    )


def _structured_data_for(obj: Any, *, title: str, description: str, image: str) -> dict:
    """Generate sensible JSON-LD for known model types. Empty dict if unknown."""
    if obj is None:
        return {
            '@context': 'https://schema.org',
            '@type': 'Organization',
            'name': getattr(settings, 'STORE_NAME', 'Morpheus Store'),
        }
    cls_name = type(obj).__name__
    if cls_name == 'Product':
        try:
            price_amount = str(obj.price.amount) if obj.price else ''
            price_currency = str(obj.price.currency) if obj.price else 'USD'
        except Exception:  # noqa: BLE001 — degrade gracefully on price-field oddities
            price_amount = ''
            price_currency = 'USD'
        return {
            '@context': 'https://schema.org',
            '@type': 'Product',
            'name': title or getattr(obj, 'name', ''),
            'description': description or getattr(obj, 'short_description', ''),
            'image': [image] if image else [],
            'sku': getattr(obj, 'sku', ''),
            'offers': {
                '@type': 'Offer',
                'price': price_amount,
                'priceCurrency': price_currency,
                'availability': 'https://schema.org/InStock',
            },
        }
    if cls_name in ('Category', 'Collection'):
        return {
            '@context': 'https://schema.org',
            '@type': 'CollectionPage',
            'name': title or getattr(obj, 'name', ''),
            'description': description or getattr(obj, 'description', ''),
        }
    return {}


# ── Sitemap ────────────────────────────────────────────────────────────────────


def iter_sitemap_entries() -> Iterable[dict]:
    """
    Yield entries that should appear in the sitemap. Pulls from:
      1. Active products (catalog)
      2. Active categories (catalog)
      3. Active collections (catalog)
      4. Manually-curated SitemapEntry rows
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
                'loc': urljoin(base, f'/products/?category={c.slug}'),
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


def render_sitemap_xml() -> str:
    parts = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for e in iter_sitemap_entries():
        parts.append('<url>')
        parts.append(f'<loc>{escape(e["loc"])}</loc>')
        if e.get('lastmod'):
            parts.append(f'<lastmod>{escape(e["lastmod"])}</lastmod>')
        if e.get('changefreq'):
            parts.append(f'<changefreq>{escape(e["changefreq"])}</changefreq>')
        if e.get('priority'):
            parts.append(f'<priority>{escape(e["priority"])}</priority>')
        parts.append('</url>')
    parts.append('</urlset>')
    return ''.join(parts)


def render_robots_txt() -> str:
    base = _site_base_url()
    lines = [
        'User-agent: *',
        'Allow: /',
        'Disallow: /admin/',
        'Disallow: /dashboard/',
        'Disallow: /auth/',
        'Disallow: /cart/',
        'Disallow: /checkout/',
        f'Sitemap: {urljoin(base, "/sitemap.xml")}',
    ]
    return '\n'.join(lines) + '\n'


def _site_base_url() -> str:
    base = getattr(settings, 'SITE_BASE_URL', '').rstrip('/')
    if base:
        return base + '/'
    hosts = getattr(settings, 'ALLOWED_HOSTS', []) or ['localhost']
    return f'https://{hosts[0]}/'


# ── Redirect resolution ────────────────────────────────────────────────────────


def resolve_redirect(path: str) -> tuple[str, int] | None:
    """Return (target_path, status_code) for `path`, or None if no alias exists."""
    from django.db import DatabaseError
    from django.utils import timezone

    from plugins.installed.seo.models import Redirect

    try:
        row = Redirect.objects.filter(from_path=path, is_active=True).first()
    except DatabaseError as e:
        logger.warning('seo: redirect lookup db error: %s', e)
        return None
    if row is None:
        return None
    try:
        Redirect.objects.filter(pk=row.pk).update(
            hit_count=row.hit_count + 1,
            last_hit_at=timezone.now(),
        )
    except DatabaseError:
        pass
    return row.to_path, row.status_code


# ── Autofill via ai_content (optional) ─────────────────────────────────────────


def autofill_meta_for(obj: Any) -> 'SeoMeta | None':  # noqa: F821
    """If the merchant left meta fields blank, fill them with sensible defaults
    derived from the host model. The AI plugin can override this later."""
    from django.contrib.contenttypes.models import ContentType

    from plugins.installed.seo.models import SeoMeta

    ct = ContentType.objects.get_for_model(type(obj))
    meta, _ = SeoMeta.objects.get_or_create(content_type=ct, object_id=str(obj.pk))

    if not meta.title:
        meta.title = (
            f'{getattr(obj, "name", "")} — {getattr(settings, "STORE_NAME", "Morpheus Store")}'
        ).strip(' —')
    if not meta.description:
        desc = getattr(obj, 'short_description', '') or getattr(obj, 'description', '')
        meta.description = (desc or '')[:300]
    if not meta.og_image:
        primary = getattr(obj, 'primary_image', None)
        if primary and getattr(primary, 'image', None):
            try:
                meta.og_image = primary.image.url
            except Exception:  # noqa: BLE001 — image may not have a URL on disk
                pass
    if not meta.auto_filled:
        meta.auto_filled = True
    meta.save()
    return meta


# ─────────────────────────────────────────────────────────────────────────────
# Deep SEO: structured data builders, LLM discovery feeds, audit/scoring.
# ─────────────────────────────────────────────────────────────────────────────

import re
from datetime import timedelta


def site_settings():
    """Return SiteSeoSettings singleton, fallback to fresh in-memory if DB empty."""
    try:
        from plugins.installed.seo.models import SiteSeoSettings
        return SiteSeoSettings.objects.first() or SiteSeoSettings(
            organization_name='', twitter_card_default='summary_large_image',
        )
    except Exception:  # noqa: BLE001
        from plugins.installed.seo.models import SiteSeoSettings
        return SiteSeoSettings(organization_name='')


def _jsonld_dump(obj: dict) -> str:
    import json as _json
    return _json.dumps(obj, separators=(',', ':'), ensure_ascii=False)


def organization_jsonld() -> dict | None:
    s = site_settings()
    if not s.organization_name:
        return None
    same_as = [u for u in (s.facebook_url, s.instagram_url, s.linkedin_url,
                           s.youtube_url, s.tiktok_url) if u]
    out = {
        '@context': 'https://schema.org',
        '@type': 'Organization',
        'name': s.organization_name,
        'url': _site_base_url(),
    }
    if s.organization_logo_url:
        out['logo'] = s.organization_logo_url
    if same_as:
        out['sameAs'] = same_as
    return out


def website_jsonld() -> dict | None:
    s = site_settings()
    base = _site_base_url()
    out = {
        '@context': 'https://schema.org',
        '@type': 'WebSite',
        'url': base,
    }
    if s.organization_name:
        out['name'] = s.organization_name
    if s.enable_sitelinks_search:
        out['potentialAction'] = {
            '@type': 'SearchAction',
            'target': f'{base}/search/?q={{search_term_string}}',
            'query-input': 'required name=search_term_string',
        }
    return out


def breadcrumb_jsonld(items: list[dict]) -> dict:
    """`items` = [{'name': str, 'url': str}, …] in order."""
    return {
        '@context': 'https://schema.org',
        '@type': 'BreadcrumbList',
        'itemListElement': [
            {'@type': 'ListItem', 'position': i + 1,
             'name': it['name'], 'item': it['url']}
            for i, it in enumerate(items)
        ],
    }


def product_jsonld(product, *, base_url: str = '') -> dict:
    """Rich Product structured data including offer, availability, brand,
    sku, image, aggregateRating if reviews exist."""
    base = base_url or _site_base_url()
    url = f'{base.rstrip("/")}/products/{product.slug}/'
    out: dict = {
        '@context': 'https://schema.org',
        '@type': 'Product',
        'name': product.name,
        'sku': product.sku,
        'url': url,
        'description': (product.short_description or product.description or '')[:500],
    }
    primary = getattr(product, 'primary_image', None)
    if primary and getattr(primary, 'image', None):
        out['image'] = primary.image.url
    if getattr(product, 'category_id', None):
        out['category'] = product.category.name

    # Offer
    price = getattr(product, 'price', None)
    if price is not None:
        avail = 'https://schema.org/InStock'
        try:
            from plugins.installed.inventory.models import StockLevel
            from django.db.models import Sum, F
            stock = StockLevel.objects.filter(variant__product=product).aggregate(
                qty=Sum(F('quantity') - F('reserved_quantity'))
            )['qty'] or 0
            if stock <= 0:
                avail = 'https://schema.org/OutOfStock'
        except Exception:  # noqa: BLE001
            pass
        out['offers'] = {
            '@type': 'Offer',
            'price': str(getattr(price, 'amount', price)),
            'priceCurrency': str(getattr(price, 'currency', 'USD')),
            'availability': avail,
            'url': url,
        }

    # Aggregate rating
    try:
        from django.db.models import Avg, Count
        agg = product.reviews.aggregate(avg=Avg('rating'), n=Count('id'))
        if agg['n']:
            out['aggregateRating'] = {
                '@type': 'AggregateRating',
                'ratingValue': round(float(agg['avg'] or 0), 1),
                'reviewCount': agg['n'],
            }
    except Exception:  # noqa: BLE001
        pass

    # AI shopping hint — `agent_metadata` already structured for agents.
    am = getattr(product, 'agent_metadata', None)
    if am:
        out['additionalProperty'] = [
            {'@type': 'PropertyValue', 'name': k, 'value': str(v)[:200]}
            for k, v in (am if isinstance(am, dict) else {}).items()
        ][:25]

    return out


def article_jsonld(*, headline: str, body: str, url: str,
                   author: str = '', published_at=None, image: str = '') -> dict:
    out = {
        '@context': 'https://schema.org',
        '@type': 'Article',
        'headline': headline[:110],
        'url': url,
        'articleBody': body[:5000],
    }
    if author:
        out['author'] = {'@type': 'Person', 'name': author}
    if published_at:
        out['datePublished'] = published_at.isoformat()
    if image:
        out['image'] = image
    return out


def faq_jsonld(qa: list[dict]) -> dict:
    return {
        '@context': 'https://schema.org',
        '@type': 'FAQPage',
        'mainEntity': [
            {'@type': 'Question', 'name': item['q'],
             'acceptedAnswer': {'@type': 'Answer', 'text': item['a']}}
            for item in qa
        ],
    }


# ─────────────────────────────────────────────────────────────────────────────
# LLM discovery: /llms.txt + /llms-full.txt + /ai/products.json
# ─────────────────────────────────────────────────────────────────────────────


def render_llms_txt(*, full: bool = False) -> str:
    """Generate /llms.txt (compact) or /llms-full.txt (with product summaries).

    Format follows the emerging llmstxt.org convention:
        # Site name
        > Short summary
        ## Section
        - [Title](url): description
    """
    s = site_settings()
    base = _site_base_url()
    name = s.organization_name or 'Morpheus store'
    out = [f'# {name}', '']
    if s.llms_txt_intro:
        out.extend(['> ' + s.llms_txt_intro.strip(), ''])
    else:
        out.extend([f'> {name} — visit {base} to browse.', ''])

    out.extend(['## Site map', f'- [Home]({base}/)',
                f'- [All products]({base}/products/)',
                f'- [Categories]({base}/categories/)',
                f'- [Search]({base}/search/?q=)',
                f'- [Sitemap XML]({base}/sitemap.xml)', ''])

    try:
        from plugins.installed.catalog.models import Category, Product
        out.append('## Categories')
        for c in Category.objects.filter(parent__isnull=True).order_by('name')[:50]:
            out.append(f'- [{c.name}]({base}/products/?category={c.slug})')
        out.append('')

        out.append('## Products')
        qs = Product.objects.filter(status='active').order_by('-created_at')
        limit = 200 if full else 50
        for p in qs[:limit]:
            line = f'- [{p.name}]({base}/products/{p.slug}/)'
            if full:
                desc = (p.short_description or p.description or '')[:160]
                if desc:
                    line += f': {desc}'
            out.append(line)
    except Exception:  # noqa: BLE001
        pass
    return '\n'.join(out) + '\n'


def render_ai_products_feed(*, limit: int = 500) -> dict:
    """Schema.org Product feed for AI shopping crawlers.

    Returns a dict that the view JSON-encodes. Each entry is a full
    Product JSON-LD object plus an `agent_metadata` block for any
    structured fields the merchant set on the Product.
    """
    out = {
        '@context': 'https://schema.org',
        '@type': 'ItemList',
        'name': site_settings().organization_name or 'Morpheus product feed',
        'itemListElement': [],
    }
    try:
        from plugins.installed.catalog.models import Product
        for i, p in enumerate(Product.objects.filter(status='active').order_by('-created_at')[:max(1, min(int(limit), 2000))]):
            out['itemListElement'].append({
                '@type': 'ListItem',
                'position': i + 1,
                'item': product_jsonld(p),
            })
    except Exception:  # noqa: BLE001
        pass
    return out


# ─────────────────────────────────────────────────────────────────────────────
# SEO audit / scoring
# ─────────────────────────────────────────────────────────────────────────────


def audit_product(product) -> dict:
    """Run SEO checks against a Product. Returns {score, issues, suggestions}."""
    s = site_settings()
    issues: list[dict] = []
    suggestions: list[str] = []
    score = 100

    meta = SeoMeta.for_obj(product) if hasattr(SeoMeta, 'for_obj') else None
    title = (meta.title if meta and meta.title else product.name) or ''
    desc = (meta.description if meta and meta.description
            else (product.short_description or product.description or ''))[:500]

    # Title
    if not title:
        issues.append({'code': 'no_title', 'severity': 'high', 'message': 'No title set.'})
        score -= 25
    elif len(title) < 30:
        issues.append({'code': 'short_title', 'severity': 'medium',
                       'message': f'Title is {len(title)} chars; aim for 30–60.'})
        score -= 10
        suggestions.append('Lengthen the title to 30–60 characters.')
    elif len(title) > s.title_max_length:
        issues.append({'code': 'long_title', 'severity': 'medium',
                       'message': f'Title is {len(title)} chars; SERP truncates around {s.title_max_length}.'})
        score -= 10
        suggestions.append(f'Trim the title to under {s.title_max_length} chars.')

    # Description
    if not desc:
        issues.append({'code': 'no_description', 'severity': 'high', 'message': 'No description.'})
        score -= 25
        suggestions.append('Write a 120–155 character description with the product\'s benefit.')
    elif len(desc) < 80:
        issues.append({'code': 'short_description', 'severity': 'medium',
                       'message': f'Description is {len(desc)} chars; aim for 120–155.'})
        score -= 10
    elif len(desc) > s.description_max_length:
        issues.append({'code': 'long_description', 'severity': 'low',
                       'message': f'Description is {len(desc)} chars; aim for under {s.description_max_length}.'})
        score -= 5

    # Image alt
    primary = getattr(product, 'primary_image', None)
    if primary is None:
        issues.append({'code': 'no_image', 'severity': 'medium', 'message': 'No primary image.'})
        score -= 10
        suggestions.append('Add a primary product image.')
    elif not getattr(primary, 'alt_text', '').strip():
        issues.append({'code': 'no_alt', 'severity': 'low',
                       'message': 'Primary image lacks alt text.'})
        score -= 5
        suggestions.append('Add descriptive alt text to the primary image.')

    # Slug
    if not product.slug or product.slug.startswith('product-'):
        issues.append({'code': 'weak_slug', 'severity': 'medium',
                       'message': 'Slug is auto-generated or generic.'})
        score -= 10
        suggestions.append('Set a human-readable slug.')

    # Canonical
    if meta and meta.canonical_url and not meta.canonical_url.startswith(_site_base_url()):
        issues.append({'code': 'external_canonical', 'severity': 'low',
                       'message': 'Canonical points off-domain.'})
        score -= 5

    # Robots
    if meta and 'noindex' in (meta.robots or ''):
        issues.append({'code': 'noindex', 'severity': 'high',
                       'message': 'Product is set to noindex.'})
        score -= 30
        suggestions.append('Remove the noindex directive unless intentional.')

    return {
        'score': max(0, min(100, score)),
        'issues': issues,
        'suggestions': suggestions,
    }


def store_audit(product, result: dict) -> 'SeoAuditResult':  # noqa: F821
    from plugins.installed.seo.models import SeoAuditResult
    from django.contrib.contenttypes.models import ContentType

    ct = ContentType.objects.get_for_model(type(product))
    audit, _ = SeoAuditResult.objects.update_or_create(
        content_type=ct, object_id=str(product.pk),
        defaults={
            'score': int(result.get('score', 0)),
            'issues': result.get('issues', []),
            'suggestions': result.get('suggestions', []),
        },
    )
    return audit


def audit_all_products(*, limit: int = 500) -> int:
    """Run audit_product on every active product. Returns count audited."""
    from plugins.installed.catalog.models import Product
    n = 0
    for product in Product.objects.filter(status='active').order_by('-updated_at')[:limit]:
        store_audit(product, audit_product(product))
        n += 1
    return n


# ─────────────────────────────────────────────────────────────────────────────
# 404 monitor + auto-redirect suggester
# ─────────────────────────────────────────────────────────────────────────────


def record_404(*, path: str, referrer: str = '') -> None:
    from plugins.installed.seo.models import NotFoundLog
    from django.db.models import F as _F
    if not path or len(path) > 500:
        return
    try:
        existing = NotFoundLog.objects.filter(path=path).first()
        if existing:
            NotFoundLog.objects.filter(pk=existing.pk).update(hit_count=_F('hit_count') + 1)
        else:
            NotFoundLog.objects.create(path=path, referrer=referrer[:500])
    except Exception:  # noqa: BLE001
        pass


def suggest_redirect(path: str) -> str:
    """Best-effort: find a product/category whose slug matches a token in `path`."""
    if not path:
        return ''
    slug_token = re.sub(r'[^a-z0-9-]', ' ', path.lower()).split()
    if not slug_token:
        return ''
    try:
        from plugins.installed.catalog.models import Category, Product
        for token in slug_token:
            if not token:
                continue
            p = Product.objects.filter(slug__icontains=token, status='active').first()
            if p:
                return f'/products/{p.slug}/'
            c = Category.objects.filter(slug__icontains=token).first()
            if c:
                return f'/products/?category={c.slug}'
    except Exception:  # noqa: BLE001
        pass
    return ''


def refresh_404_suggestions(*, limit: int = 50) -> int:
    """Fill in suggested_target on the top unresolved 404s."""
    from plugins.installed.seo.models import NotFoundLog
    n = 0
    rows = NotFoundLog.objects.filter(is_resolved=False).order_by('-hit_count')[:limit]
    for row in rows:
        if row.suggested_target:
            continue
        target = suggest_redirect(row.path)
        if target:
            row.suggested_target = target
            row.save(update_fields=['suggested_target'])
            n += 1
    return n
