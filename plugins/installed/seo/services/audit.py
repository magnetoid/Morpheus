"""Per-product SEO audit + auto-link suggestions.

``audit_product`` produces a ``{score, issues, suggestions}`` triple
that the dashboard renders into a checklist. Persistence happens via
``store_audit`` (one ``SeoAuditResult`` row per product, idempotent).
"""
from __future__ import annotations

import re

from ._helpers import _site_base_url, logger, site_settings


def audit_product(product) -> dict:
    """Run SEO checks against a Product. Returns {score, issues, suggestions}."""
    from plugins.installed.seo.models import SeoMeta

    s = site_settings()
    issues: list[dict] = []
    suggestions: list[str] = []
    score = 100

    meta = SeoMeta.for_obj(product) if hasattr(SeoMeta, 'for_obj') else None
    title = (meta.title if meta and meta.title else product.name) or ''
    # `desc_explicit` is True only when the merchant set a SeoMeta override;
    # in that case the over-length rule is meaningful (the value is going
    # into <meta name="description">). When falling back to the rich
    # product.short_description we only enforce the lower bound — going
    # long on storefront copy is fine and the meta tag is auto-truncated.
    desc_explicit = bool(meta and meta.description)
    desc = (meta.description if desc_explicit
            else (product.short_description or product.description or ''))[:500]

    # Title — short-title rule only applies to explicit SeoMeta.title;
    # the product name is whatever the merchant put on the product
    # (e.g. "Pinocchio") and may legitimately be shorter than 30 chars.
    title_explicit = bool(meta and meta.title)
    if not title:
        issues.append({'code': 'no_title', 'severity': 'high', 'message': 'No title set.'})
        score -= 25
    elif title_explicit and len(title) < 30:
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
    elif desc_explicit and len(desc) > s.description_max_length:
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

    # Content-quality rules (2026 AEO/GEO):
    # AI search engines cite long-form, well-structured content far more
    # than thin product copy. These penalties cap at -25 collectively so
    # they nudge rather than dominate the score.
    body_html = (product.description or '')
    body_text = re.sub(r'<[^>]+>', ' ', body_html)
    body_text = re.sub(r'\s+', ' ', body_text).strip()
    word_count = len(body_text.split()) if body_text else 0
    content_penalty = 0
    if word_count < 100:
        issues.append({'code': 'thin_description', 'severity': 'medium',
                       'message': f'Description is {word_count} words; AI search cites long-form content 10× more.'})
        content_penalty += 10
        suggestions.append('Expand the description to at least 200 words — AI engines cite longer pages disproportionately.')

    internal_links = (
        len(re.findall(r'<a\s+[^>]*href=', body_html, flags=re.I))
        + len(re.findall(r'\[[^\]]+\]\([^)]+\)', body_html))
    )
    if internal_links == 0 and word_count >= 80:
        issues.append({'code': 'no_internal_links', 'severity': 'low',
                       'message': 'Description has no internal links.'})
        content_penalty += 5
        suggestions.append('Add 1–3 internal links (related books, the author page, the category) inside the description.')

    if primary is not None:
        alt = (getattr(primary, 'alt_text', '') or '').strip()
        alt_lower = alt.lower()
        if alt and len(alt) < 8:
            issues.append({'code': 'short_alt', 'severity': 'low',
                           'message': f'Primary image alt is only {len(alt)} chars.'})
            content_penalty += 3
            suggestions.append('Describe the image in 8+ chars — what is visible, not the product name.')
        elif alt_lower in {'image', 'photo', 'picture', 'cover'}:
            issues.append({'code': 'generic_alt', 'severity': 'low',
                           'message': f'Primary image alt is generic ("{alt}").'})
            content_penalty += 3
            suggestions.append('Replace generic alt text with a sentence that describes what is in the image.')
        elif alt and product.name and alt_lower == product.name.lower():
            issues.append({'code': 'duplicate_alt', 'severity': 'low',
                           'message': 'Alt text just repeats the product name.'})
            content_penalty += 2

    if word_count >= 300:
        heading_count = (
            len(re.findall(r'<h[23]\b', body_html, flags=re.I))
            + len(re.findall(r'(?m)^\s*#{2,3}\s+\S', body_html))
        )
        if heading_count == 0:
            issues.append({'code': 'no_subheadings', 'severity': 'low',
                           'message': 'Long description has no H2/H3 subheadings — bad for scanning + AI extraction.'})
            content_penalty += 5
            suggestions.append('Break the long description with 2–3 H2 subheadings (the gist, the form, who it\'s for).')

    score -= min(content_penalty, 25)

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


def suggest_internal_links_for(product, *, limit: int = 3) -> list[dict]:
    """Return up to ``limit`` related products as link-suggestion dicts.

    Uses `ai_assistant.recommendations.similar_to` (embedding +
    category fallback). Returned shape:
    ``[{'slug': str, 'name': str, 'url': str}, ...]``. Skipped products
    are filtered (drafts, missing slug).
    """
    try:
        from plugins.installed.ai_assistant.services.recommendations import similar_to
    except Exception:  # noqa: BLE001
        return []
    try:
        rows = similar_to(product, limit=max(int(limit), 1))
    except Exception as exc:  # noqa: BLE001
        logger.debug('suggest_internal_links: similar_to failed: %s', exc)
        return []
    base = _site_base_url().rstrip('/')
    out = []
    for p in rows:
        slug = getattr(p, 'slug', '') or ''
        name = getattr(p, 'name', '') or ''
        if not slug or not name:
            continue
        out.append({'slug': slug, 'name': name, 'url': f'{base}/products/{slug}/'})
    return out[:limit]
