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
            # Append AI-snippet directives unless the merchant explicitly
            # set noindex — these unlock full AI Overview snippets +
            # large image previews without changing index behaviour.
            ai_directives = 'max-snippet:-1, max-image-preview:large, max-video-preview:-1'
            robots = self.robots if 'noindex' in self.robots else f'{self.robots}, {ai_directives}'
            parts.append(f'<meta name="robots" content="{escape(robots)}">')
        if self.canonical_url:
            parts.append(f'<link rel="canonical" href="{escape(self.canonical_url)}">')

        og_title = self.og_title or self.title
        og_desc = self.og_description or self.description
        if og_title:
            parts.append(f'<meta property="og:title" content="{escape(og_title)}">')
        if og_desc:
            parts.append(f'<meta property="og:description" content="{escape(og_desc)}">')
        parts.append(f'<meta property="og:type" content="{escape(self.og_type)}">')
        # og:locale — matches the Content-Language header the markets
        # middleware emits; falls back to en_US.
        try:
            from django.conf import settings as _s
            locale = (getattr(_s, 'LANGUAGE_CODE', 'en-US') or 'en-US').replace('-', '_')
        except Exception:  # noqa: BLE001
            locale = 'en_US'
        parts.append(f'<meta property="og:locale" content="{escape(locale)}">')
        if self.og_image:
            parts.append(f'<meta property="og:image" content="{escape(self.og_image)}">')
            parts.append(f'<meta property="og:image:secure_url" content="{escape(self.og_image)}">')
            parts.append('<meta property="og:image:width" content="1200">')
            parts.append('<meta property="og:image:height" content="630">')
            if og_title:
                parts.append(f'<meta property="og:image:alt" content="{escape(og_title)}">')

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
    """Merge per-object SeoMeta + native model SEO fields + fallbacks.

    Priority order (highest first):
      1. SeoMeta row (generic-FK overrides — admin can set anything)
      2. Native model SEO fields (Product.og_title, focus_keyword, …)
      3. Provided fallbacks (whatever the caller passed)
    """
    from plugins.installed.seo.models import SeoMeta

    meta = SeoMeta.for_obj(obj) if obj is not None else None

    def native(name: str, default: str = '') -> str:
        # Pull a SEO field directly off the model instance, dict-safe.
        if obj is None:
            return default
        if isinstance(obj, dict):
            return str(obj.get(name) or default)
        return str(getattr(obj, name, '') or default)

    title = (
        (meta.title if meta and meta.title else '')
        or native('meta_title')
        or fallback_title
    ).strip()
    description = (
        (meta.description if meta and meta.description else '')
        or native('meta_description')
        or fallback_description
    ).strip()
    og_image = (meta.og_image if meta and meta.og_image else fallback_image).strip()
    canonical = (
        (meta.canonical_url if meta and meta.canonical_url else '')
        or native('canonical_url')
        or canonical_url
    ).strip()

    # Robots: SeoMeta wins; else use the model's noindex/nofollow flags.
    if meta:
        robots = meta.robots
    else:
        flags = []
        flags.append('noindex' if (obj is not None and (
            obj.get('noindex') if isinstance(obj, dict) else getattr(obj, 'noindex', False)
        )) else 'index')
        flags.append('nofollow' if (obj is not None and (
            obj.get('nofollow') if isinstance(obj, dict) else getattr(obj, 'nofollow', False)
        )) else 'follow')
        robots = ', '.join(flags)

    keywords = (meta.keywords if meta and meta.keywords else '') or native('focus_keyword')
    twitter_card = (
        (meta.twitter_card if meta else '')
        or native('twitter_card')
        or 'summary_large_image'
    )
    og_title = (meta.og_title if meta and meta.og_title else '') or native('og_title')
    og_description = (
        (meta.og_description if meta and meta.og_description else '')
        or native('og_description')
    )
    type_ = (meta.og_type if meta and meta.og_type else og_type)

    structured = _structured_data_for(obj, title=title, description=description, image=og_image)
    # Merge native model structured_data (Product.structured_data) → SeoMeta (most specific wins).
    if obj is not None and not isinstance(obj, dict):
        native_sd = getattr(obj, 'structured_data', None)
        if isinstance(native_sd, dict) and native_sd:
            structured = {**structured, **native_sd}
    if meta and meta.structured_data:
        structured = {**structured, **meta.structured_data}

    return ResolvedMeta(
        title=title,
        description=description,
        og_title=og_title,
        og_description=og_description,
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


#: 2026 AI/answer-engine crawler catalogue. Each entry: (UA, label,
# behaviour). Default policy = "allow" for every retrieval bot — they
# drive AI Overviews / ChatGPT / Perplexity citations. Training-only
# bots default to "allow" too so the merchant opts out, not in.
AI_CRAWLERS = [
    # OpenAI
    ('GPTBot',           'OpenAI · ChatGPT training crawler',          'training'),
    ('OAI-SearchBot',    'OpenAI · ChatGPT Search retrieval',          'search'),
    ('ChatGPT-User',     'OpenAI · ChatGPT user-triggered fetch',      'user'),
    # Anthropic
    ('ClaudeBot',        'Anthropic · Claude training crawler',        'training'),
    ('Claude-User',      'Anthropic · Claude user-triggered fetch',    'user'),
    ('Claude-SearchBot', 'Anthropic · Claude search retrieval',        'search'),
    # Perplexity
    ('PerplexityBot',    'Perplexity · indexing crawler',              'search'),
    ('Perplexity-User',  'Perplexity · user-triggered fetch',          'user'),
    # Google
    ('Google-Extended',  'Google · Bard / Vertex AI training opt-out', 'training'),
    # Apple
    ('Applebot-Extended','Apple · Apple Intelligence training opt-out','training'),
    # Meta
    ('Meta-ExternalAgent','Meta · AI training crawler',                'training'),
    # ByteDance (TikTok)
    ('Bytespider',       'ByteDance · LLM training crawler',           'training'),
    # Amazon
    ('Amazonbot',        'Amazon · Alexa + AI fetcher',                'search'),
    # Common Crawl
    ('CCBot',            'Common Crawl · public web archive',          'training'),
]


def get_ai_crawler_policy() -> dict[str, bool]:
    """Read per-bot allow/disallow policy from seo plugin config.

    Default = all-allow. Stored as ``{ua_lowercase: bool}`` in the plugin
    config JSON. Returns the merged map ready for robots.txt emission.
    """
    try:
        from plugins.registry import plugin_registry
        seo_plugin = plugin_registry.get('seo')
        if seo_plugin is None:
            return {}
        raw = seo_plugin.get_config_value('ai_crawler_policy', {}) or {}
        if not isinstance(raw, dict):
            return {}
        return {k.lower(): bool(v) for k, v in raw.items()}
    except Exception:  # noqa: BLE001 — never break robots.txt over a config miss
        return {}


def render_robots_txt() -> str:
    """robots.txt with explicit AI-crawler blocks.

    A 2026 storefront wants per-bot control: opt out of LLM training
    crawlers without blocking the retrieval bots that drive AI Overviews
    + ChatGPT/Perplexity citations. Order matters — specific UAs first,
    then the universal ``User-agent: *`` fallback.
    """
    base = _site_base_url()
    policy = get_ai_crawler_policy()  # {ua_lowercase: True=allow / False=block}
    common_disallow = [
        'Disallow: /admin/',
        'Disallow: /dashboard/',
        'Disallow: /auth/',
        'Disallow: /cart/',
        'Disallow: /checkout/',
    ]

    lines: list[str] = []

    # Per-bot blocks. Default is "allow" — we only emit a block when the
    # merchant has explicitly disallowed a bot.
    for ua, _label, _kind in AI_CRAWLERS:
        allowed = policy.get(ua.lower(), True)
        lines.append(f'User-agent: {ua}')
        if allowed:
            lines.append('Allow: /')
            lines.extend(common_disallow)
        else:
            lines.append('Disallow: /')
        lines.append('')

    # Universal fallback for every other crawler (Googlebot, Bingbot, …).
    lines.extend([
        'User-agent: *',
        'Allow: /',
        *common_disallow,
        '',
        f'Sitemap: {urljoin(base, "/sitemap.xml")}',
        f'Sitemap: {urljoin(base, "/sitemap-images.xml")}',
    ])
    return '\n'.join(lines).rstrip() + '\n'


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


def _seo_plugin_cfg() -> dict:
    """Read seo plugin's PluginConfig JSON. Used for fields that don't
    warrant a model migration (return policy, shipping fee, IndexNow
    key, AI crawler matrix, etc.). Returns ``{}`` when the plugin is
    not loaded yet (early boot / tests)."""
    try:
        from plugins.registry import plugin_registry
        p = plugin_registry.get('seo')
        if p is None:
            return {}
        return p.get_config() or {}
    except Exception:  # noqa: BLE001
        return {}


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
    """Rich Product structured data.

    `product` may be a Django model instance (SSR path) OR a dict (when
    fed by GraphQL via a template tag). Accessor helper normalises both.
    """
    base = base_url or _site_base_url()

    def g(name, default=None):
        if isinstance(product, dict):
            return product.get(name, default)
        return getattr(product, name, default)

    slug = g('slug') or ''
    if not slug:
        return {}

    url = f'{base.rstrip("/")}/products/{slug}/'
    description = g('short_description') or g('description') or ''
    out: dict = {
        '@context': 'https://schema.org',
        '@type': 'Product',
        'name': g('name') or '',
        'sku': g('sku') or '',
        'url': url,
        'description': description[:500],
    }

    # Image: model exposes .primary_image.image.url; GraphQL exposes
    # primary_image_url or primaryImage.url.
    primary = g('primary_image')
    if primary:
        if isinstance(primary, dict):
            out['image'] = primary.get('url') or primary.get('image_url') or ''
        elif getattr(primary, 'image', None):
            out['image'] = primary.image.url
    elif g('primary_image_url'):
        out['image'] = g('primary_image_url')

    # Category: model has .category.name; dict has .category as nested.
    cat = g('category')
    if cat:
        out['category'] = cat.get('name') if isinstance(cat, dict) else getattr(cat, 'name', '')

    # Offer
    price = g('price')
    if price is not None:
        avail = 'https://schema.org/InStock'
        # Stock check is ORM-only; skip silently for dicts.
        try:
            if not isinstance(product, dict):
                from plugins.installed.inventory.models import StockLevel
                from django.db.models import Sum, F
                stock = StockLevel.objects.filter(variant__product=product).aggregate(
                    qty=Sum(F('quantity') - F('reserved_quantity'))
                )['qty'] or 0
                if stock <= 0:
                    avail = 'https://schema.org/OutOfStock'
        except Exception:  # noqa: BLE001
            pass
        if isinstance(price, dict):
            offer_price = str(price.get('amount', ''))
            offer_curr = str(price.get('currency', 'USD'))
        else:
            offer_price = str(getattr(price, 'amount', price))
            offer_curr = str(getattr(price, 'currency', 'USD'))
        out['offers'] = {
            '@type': 'Offer',
            'price': offer_price,
            'priceCurrency': offer_curr,
            'availability': avail,
            'url': url,
        }
        # MerchantReturnPolicy + OfferShippingDetails — 2026 Required
        # for Merchant free listings + AI shopping comparisons. Values
        # live in the SEO plugin's PluginConfig JSON so no migration.
        commerce_cfg = _seo_plugin_cfg()
        return_days = int(commerce_cfg.get('return_days') or 0)
        ship_fee = commerce_cfg.get('shipping_fee_amount') or '0'
        free_over = commerce_cfg.get('free_shipping_over') or '0'
        country = (commerce_cfg.get('shipping_country') or 'US').upper()
        if return_days:
            out['offers']['hasMerchantReturnPolicy'] = {
                '@type': 'MerchantReturnPolicy',
                'applicableCountry': country,
                'returnPolicyCategory': 'https://schema.org/MerchantReturnFiniteReturnWindow',
                'merchantReturnDays': return_days,
                'returnMethod': 'https://schema.org/ReturnByMail',
                'returnFees': 'https://schema.org/FreeReturn',
            }
        out['offers']['shippingDetails'] = {
            '@type': 'OfferShippingDetails',
            'shippingDestination': {
                '@type': 'DefinedRegion',
                'addressCountry': country,
            },
            'shippingRate': {
                '@type': 'MonetaryAmount',
                'value': str(ship_fee),
                'currency': offer_curr,
            },
            'deliveryTime': {
                '@type': 'ShippingDeliveryTime',
                'handlingTime': {
                    '@type': 'QuantitativeValue',
                    'minValue': 0, 'maxValue': 1, 'unitCode': 'DAY',
                },
                'transitTime': {
                    '@type': 'QuantitativeValue',
                    'minValue': 2, 'maxValue': 5, 'unitCode': 'DAY',
                },
            },
        }
        if free_over:
            out['offers']['shippingDetails']['freeShippingThreshold'] = {
                '@type': 'MonetaryAmount',
                'value': str(free_over),
                'currency': offer_curr,
            }

    # Aggregate rating — ORM only.
    if not isinstance(product, dict):
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
    am = g('agent_metadata')
    if am:
        out['additionalProperty'] = [
            {'@type': 'PropertyValue', 'name': k, 'value': str(v)[:200]}
            for k, v in (am if isinstance(am, dict) else {}).items()
        ][:25]

    # ProductGroup variants — schema.org's hasVariant unlocks variant
    # cards in Google AI Shopping. Only emit when variants exist.
    if not isinstance(product, dict):
        try:
            variants = list(getattr(product, 'variants', None).filter(is_active=True)[:20]) \
                if getattr(product, 'variants', None) else []
            if variants:
                out['@type'] = 'ProductGroup'
                out['productGroupID'] = str(getattr(product, 'id', '') or slug)
                out['hasVariant'] = [
                    {
                        '@type': 'Product',
                        'sku': v.sku or '',
                        'name': v.name or '',
                        'offers': {
                            '@type': 'Offer',
                            'price': str(getattr(v, 'price', None).amount if getattr(v, 'price', None) else (offer_price if price is not None else '')),
                            'priceCurrency': str(getattr(v, 'price', None).currency if getattr(v, 'price', None) else (offer_curr if price is not None else 'USD')),
                            'availability': 'https://schema.org/InStock',
                        },
                    }
                    for v in variants
                ]
        except Exception:  # noqa: BLE001
            pass

    # Entity-graph sameAs links via metafield 'seo.same_as' (comma- or
    # newline-separated URLs). March-2026 core update made this the #1
    # leverage point for AI engines.
    if not isinstance(product, dict):
        try:
            from django.contrib.contenttypes.models import ContentType
            from plugins.installed.metafields.models import Metafield
            ct = ContentType.objects.get_for_model(type(product))
            m = Metafield.objects.filter(
                content_type=ct, object_id=product.pk,
                namespace='seo', key='same_as',
            ).first()
            if m and m.value:
                urls = [u.strip() for u in str(m.value).replace('\n', ',').split(',') if u.strip()]
                if urls:
                    out['sameAs'] = urls[:10]
        except Exception:  # noqa: BLE001
            pass

    # GTIN / brand via 'book' metafield namespace (used by dotbooks).
    if not isinstance(product, dict):
        try:
            from django.contrib.contenttypes.models import ContentType
            from plugins.installed.metafields.models import Metafield
            ct = ContentType.objects.get_for_model(type(product))
            book_meta = {
                row.key: row.value for row in
                Metafield.objects.filter(
                    content_type=ct, object_id=product.pk, namespace='book',
                )
            }
            if book_meta.get('isbn'):
                out['gtin13'] = str(book_meta['isbn'])[:13]
            if book_meta.get('publisher'):
                out['brand'] = {'@type': 'Brand', 'name': str(book_meta['publisher'])}
            if book_meta.get('author'):
                out['author'] = {'@type': 'Person', 'name': str(book_meta['author'])}
        except Exception:  # noqa: BLE001
            pass

    return out


def speakable_jsonld(selectors: list[str] | None = None) -> dict:
    """SpeakableSpecification — tells voice assistants which CSS selectors
    contain text suitable for spoken reading.

    Defaults target the page's headline + the lede paragraph, which work
    on every storefront template we ship.
    """
    css = selectors or ['h1', '.lede', '[itemprop="description"]']
    return {
        '@context': 'https://schema.org',
        '@type': 'WebPage',
        'speakable': {
            '@type': 'SpeakableSpecification',
            'cssSelector': css,
        },
    }


def collection_page_jsonld(*, name: str, url: str, description: str,
                            items: list[dict]) -> dict:
    """CollectionPage + ItemList for PLP/category pages.

    Each `items[i]` is a dict with at least {name, url, image}. Tells AI
    engines that this URL is a list of products under a topic — Google
    AI Overviews use this to assemble "show me [topic] from X" answers.
    """
    return {
        '@context': 'https://schema.org',
        '@type': 'CollectionPage',
        'name': name[:120],
        'url': url,
        'description': (description or '')[:400],
        'mainEntity': {
            '@type': 'ItemList',
            'numberOfItems': len(items),
            'itemListElement': [
                {
                    '@type': 'ListItem',
                    'position': idx + 1,
                    'url': it.get('url') or '',
                    'name': (it.get('name') or '')[:120],
                    **({'image': it['image']} if it.get('image') else {}),
                }
                for idx, it in enumerate(items[:60])
            ],
        },
    }


def qa_page_jsonld(*, name: str, url: str, qa: list[dict]) -> dict:
    """QAPage schema — ChatGPT cites QAPage ~58% more than FAQPage
    (per Searchless research, May 2026). Use for any "ask a question →
    answer" surface; FAQPage stays useful for static FAQs.
    """
    return {
        '@context': 'https://schema.org',
        '@type': 'QAPage',
        'name': name[:120],
        'url': url,
        'mainEntity': [
            {
                '@type': 'Question',
                'name': item.get('q', '')[:200],
                'answerCount': 1,
                'acceptedAnswer': {
                    '@type': 'Answer',
                    'text': item.get('a', '')[:2000],
                },
            }
            for item in qa
        ],
    }


def get_or_create_indexnow_key() -> str:
    """IndexNow key — a UUID stored in plugin config, surfaced at
    ``/<key>.txt`` for verification + sent with every push.
    """
    import uuid
    cfg = _seo_plugin_cfg()
    key = cfg.get('indexnow_key') or ''
    if not key:
        key = uuid.uuid4().hex
        try:
            from plugins.registry import plugin_registry
            p = plugin_registry.get('seo')
            if p is not None:
                p.set_config('indexnow_key', key)
        except Exception:  # noqa: BLE001
            pass
    return key


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
    """News sitemap for journal posts in the last 48 h. Required-when-
    fresh by Google News + AI editorial citations (Perplexity / ChatGPT
    News). Empty urlset when no fresh posts — that's valid.
    """
    from django.utils import timezone
    base = _site_base_url().rstrip('/')
    cutoff = timezone.now() - timedelta(hours=48)
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
        'xmlns:news="http://www.google.com/schemas/sitemap-news/0.9">',
    ]
    try:
        from plugins.installed.cms.models import JournalPost
        s = site_settings()
        pub_name = s.organization_name or 'Morpheus'
        qs = JournalPost.objects.filter(
            status='published', published_at__gte=cutoff,
        ).order_by('-published_at')[:1000]
        for post in qs:
            url = f'{base}/journal/{post.slug}/'
            pub = post.published_at.replace(microsecond=0).isoformat()
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
    except Exception:  # noqa: BLE001 — no cms / no journal model
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


def render_pwa_manifest() -> dict:
    """Web App Manifest — lets browsers install the storefront as a
    PWA. Required by Lighthouse "Installable" + opens us up for the
    Android home-screen add prompt.
    """
    s = site_settings()
    name = s.organization_name or 'dot books'
    return {
        'name': name,
        'short_name': name[:12],
        'description': s.llms_txt_intro or name,
        'start_url': '/',
        'scope': '/',
        'display': 'standalone',
        'theme_color': '#f6f1e7',
        'background_color': '#f6f1e7',
        'icons': [
            {'src': '/static/icons/icon-192.png', 'sizes': '192x192', 'type': 'image/png'},
            {'src': '/static/icons/icon-512.png', 'sizes': '512x512', 'type': 'image/png'},
            {'src': '/static/icons/icon-maskable-512.png', 'sizes': '512x512',
             'type': 'image/png', 'purpose': 'maskable'},
        ],
    }


def ping_indexnow(urls: list[str]) -> dict:
    """POST one or many URLs to IndexNow — instant indexation on Bing,
    Yandex, Naver, Seznam, Yep. Fire-and-forget on the server; failures
    are silent so a slow IndexNow doesn't slow product saves.
    """
    import json as _json
    import urllib.request
    base = _site_base_url().rstrip('/')
    host = base.replace('https://', '').replace('http://', '').strip('/')
    key = get_or_create_indexnow_key()
    body = {
        'host': host,
        'key': key,
        'keyLocation': f'{base}/{key}.txt',
        'urlList': [u for u in urls if u][:10_000],
    }
    try:
        req = urllib.request.Request(
            'https://api.indexnow.org/IndexNow',
            data=_json.dumps(body).encode('utf-8'),
            headers={'Content-Type': 'application/json; charset=utf-8'},
            method='POST',
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            return {'ok': 200 <= resp.status < 300, 'status': resp.status}
    except Exception as exc:  # noqa: BLE001
        return {'ok': False, 'error': str(exc)}


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
            # Per-product markdown export — let crawlers fetch the
            # canonical content without parsing HTML. /md/products/<slug>
            md_url = f'{base}/md/products/{p.slug}'
            line = f'- [{p.name}]({base}/products/{p.slug}/) ({md_url})'
            if full:
                desc = (p.short_description or p.description or '')[:160]
                if desc:
                    line += f': {desc}'
            out.append(line)
    except Exception:  # noqa: BLE001
        pass
    return '\n'.join(out) + '\n'


def render_product_markdown(product) -> str:
    """Canonical markdown rendering of a product for LLM crawlers.

    Output is plain text — no HTML, no menu, no boilerplate. Stable
    structure so crawlers can rely on the heading shape across pages.
    Sections (each separated by a blank line):
        # Title
        > Short description
        Price · availability
        ## About
        long description
        ## Specifications
        - key: value
        ## Reviews (top 5)
    """
    parts: list[str] = []
    name = getattr(product, 'name', '') or ''
    parts.append(f'# {name}')
    short = (getattr(product, 'short_description', '') or '').strip()
    if short:
        parts.extend(['', f'> {short}'])
    # Price + availability.
    price = getattr(product, 'price', None)
    if price is not None:
        try:
            amount = price.amount
            currency = str(price.currency)
            avail = 'in stock' if not getattr(product, 'track_inventory', False) else \
                    ('in stock' if (getattr(product, 'stock_quantity', None) or 1) > 0 else 'out of stock')
            parts.extend(['', f'Price: {amount} {currency} · {avail}'])
        except Exception:  # noqa: BLE001
            pass
    desc = (getattr(product, 'description', '') or '').strip()
    if desc:
        # Strip HTML if any — naive but adequate for the editorial copy
        # this storefront stores in `description`.
        import re as _re
        plain = _re.sub(r'<[^>]+>', '', desc)
        parts.extend(['', '## About', plain])
    # Book-shop specifics — pull metafields if the catalog uses them.
    try:
        from django.contrib.contenttypes.models import ContentType
        from plugins.installed.metafields.models import Metafield
        ct = ContentType.objects.get_for_model(type(product))
        rows = list(Metafield.objects.filter(
            content_type=ct, object_id=product.pk, namespace='book',
        ).values_list('key', 'value'))
        if rows:
            parts.append('')
            parts.append('## Specifications')
            for k, v in rows:
                parts.append(f'- {k}: {v}')
    except Exception:  # noqa: BLE001
        pass
    # Reviews (top 5 published).
    try:
        from plugins.installed.catalog.models import Review
        revs = list(
            Review.objects.filter(product=product, status='published')
            .order_by('-created_at')[:5]
            .values('rating', 'title', 'body', 'created_at')
        )
        if revs:
            parts.append('')
            parts.append('## Reviews')
            for r in revs:
                parts.append(f"### {r.get('title') or '(untitled)'} — {r['rating']}/5")
                parts.append((r.get('body') or '').strip())
    except Exception:  # noqa: BLE001
        pass
    return '\n'.join(parts) + '\n'


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
