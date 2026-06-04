"""Per-product SEO audit + auto-link suggestions.

``audit_product`` produces a ``{score, issues, suggestions}`` triple
that the dashboard renders into a checklist. Persistence happens via
``store_audit`` (one ``SeoAuditResult`` row per product, idempotent).
"""

# ruff: noqa: PLC0415, I001, PLR0912, PLR0915, UP037
# Inline imports keep optional plugins (catalog, metafields, inventory,
# ai_assistant) soft so a disabled plugin can't break audit/scoring.
# The audit + AEO scorers are deliberately long, flat check-lists —
# splitting them hurts readability more than the branch count helps.
# Same convention as services/jsonld.py.

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
    desc = (
        meta.description
        if desc_explicit
        else (product.short_description or product.description or '')
    )[:500]

    # Title — short-title rule only applies to explicit SeoMeta.title;
    # the product name is whatever the merchant put on the product
    # (e.g. "Pinocchio") and may legitimately be shorter than 30 chars.
    title_explicit = bool(meta and meta.title)
    if not title:
        issues.append({'code': 'no_title', 'severity': 'high', 'message': 'No title set.'})
        score -= 25
    elif title_explicit and len(title) < 30:
        issues.append(
            {
                'code': 'short_title',
                'severity': 'medium',
                'message': f'Title is {len(title)} chars; aim for 30–60.',
            }
        )
        score -= 10
        suggestions.append('Lengthen the title to 30–60 characters.')
    elif len(title) > s.title_max_length:
        issues.append(
            {
                'code': 'long_title',
                'severity': 'medium',
                'message': f'Title is {len(title)} chars; SERP truncates around {s.title_max_length}.',
            }
        )
        score -= 10
        suggestions.append(f'Trim the title to under {s.title_max_length} chars.')

    # Description
    if not desc:
        issues.append({'code': 'no_description', 'severity': 'high', 'message': 'No description.'})
        score -= 25
        suggestions.append("Write a 120–155 character description with the product's benefit.")
    elif len(desc) < 80:
        issues.append(
            {
                'code': 'short_description',
                'severity': 'medium',
                'message': f'Description is {len(desc)} chars; aim for 120–155.',
            }
        )
        score -= 10
    elif desc_explicit and len(desc) > s.description_max_length:
        issues.append(
            {
                'code': 'long_description',
                'severity': 'low',
                'message': f'Description is {len(desc)} chars; aim for under {s.description_max_length}.',
            }
        )
        score -= 5

    # Image alt
    primary = getattr(product, 'primary_image', None)
    if primary is None:
        issues.append({'code': 'no_image', 'severity': 'medium', 'message': 'No primary image.'})
        score -= 10
        suggestions.append('Add a primary product image.')
    elif not getattr(primary, 'alt_text', '').strip():
        issues.append(
            {'code': 'no_alt', 'severity': 'low', 'message': 'Primary image lacks alt text.'}
        )
        score -= 5
        suggestions.append('Add descriptive alt text to the primary image.')

    # Slug
    if not product.slug or product.slug.startswith('product-'):
        issues.append(
            {
                'code': 'weak_slug',
                'severity': 'medium',
                'message': 'Slug is auto-generated or generic.',
            }
        )
        score -= 10
        suggestions.append('Set a human-readable slug.')

    # Canonical
    if meta and meta.canonical_url and not meta.canonical_url.startswith(_site_base_url()):
        issues.append(
            {
                'code': 'external_canonical',
                'severity': 'low',
                'message': 'Canonical points off-domain.',
            }
        )
        score -= 5

    # Robots
    if meta and 'noindex' in (meta.robots or ''):
        issues.append(
            {'code': 'noindex', 'severity': 'high', 'message': 'Product is set to noindex.'}
        )
        score -= 30
        suggestions.append('Remove the noindex directive unless intentional.')

    # Content-quality rules (2026 AEO/GEO):
    # AI search engines cite long-form, well-structured content far more
    # than thin product copy. These penalties cap at -25 collectively so
    # they nudge rather than dominate the score.
    body_html = product.description or ''
    body_text = re.sub(r'<[^>]+>', ' ', body_html)
    body_text = re.sub(r'\s+', ' ', body_text).strip()
    word_count = len(body_text.split()) if body_text else 0
    content_penalty = 0
    if word_count < 100:
        issues.append(
            {
                'code': 'thin_description',
                'severity': 'medium',
                'message': f'Description is {word_count} words; AI search cites long-form content 10× more.',
            }
        )
        content_penalty += 10
        suggestions.append(
            'Expand the description to at least 200 words — AI engines cite longer pages disproportionately.'
        )

    internal_links = len(re.findall(r'<a\s+[^>]*href=', body_html, flags=re.I)) + len(
        re.findall(r'\[[^\]]+\]\([^)]+\)', body_html)
    )
    if internal_links == 0 and word_count >= 80:
        issues.append(
            {
                'code': 'no_internal_links',
                'severity': 'low',
                'message': 'Description has no internal links.',
            }
        )
        content_penalty += 5
        suggestions.append(
            'Add 1–3 internal links (related books, the author page, the category) inside the description.'
        )

    if primary is not None:
        alt = (getattr(primary, 'alt_text', '') or '').strip()
        alt_lower = alt.lower()
        if alt and len(alt) < 8:
            issues.append(
                {
                    'code': 'short_alt',
                    'severity': 'low',
                    'message': f'Primary image alt is only {len(alt)} chars.',
                }
            )
            content_penalty += 3
            suggestions.append(
                'Describe the image in 8+ chars — what is visible, not the product name.'
            )
        elif alt_lower in {'image', 'photo', 'picture', 'cover'}:
            issues.append(
                {
                    'code': 'generic_alt',
                    'severity': 'low',
                    'message': f'Primary image alt is generic ("{alt}").',
                }
            )
            content_penalty += 3
            suggestions.append(
                'Replace generic alt text with a sentence that describes what is in the image.'
            )
        elif alt and product.name and alt_lower == product.name.lower():
            issues.append(
                {
                    'code': 'duplicate_alt',
                    'severity': 'low',
                    'message': 'Alt text just repeats the product name.',
                }
            )
            content_penalty += 2

    if word_count >= 300:
        heading_count = len(re.findall(r'<h[23]\b', body_html, flags=re.I)) + len(
            re.findall(r'(?m)^\s*#{2,3}\s+\S', body_html)
        )
        if heading_count == 0:
            issues.append(
                {
                    'code': 'no_subheadings',
                    'severity': 'low',
                    'message': 'Long description has no H2/H3 subheadings — bad for scanning + AI extraction.',
                }
            )
            content_penalty += 5
            suggestions.append(
                "Break the long description with 2–3 H2 subheadings (the gist, the form, who it's for)."
            )

    score -= min(content_penalty, 25)

    return {
        'score': max(0, min(100, score)),
        'issues': issues,
        'suggestions': suggestions,
    }


def score_aeo(product) -> dict:
    """Answer-Engine / Generative-Engine readiness score for a product.

    Distinct from ``audit_product`` (classic SERP hygiene): this scores
    how *quotable* and *citable* a page is for AI answer engines —
    ChatGPT, Perplexity, Google AI Overviews, Claude. The signals are
    the levers those engines actually weigh when deciding what to lift
    into an answer and attribute.

    Returns ``{score, signals, suggestions}`` where ``signals`` is a
    list of ``{code, label, ok, weight, detail}`` so the inspector can
    render a checklist and the merchant sees exactly what to fix.
    """
    from ._helpers import ai_answer_for

    signals: list[dict] = []
    suggestions: list[str] = []

    def add(code, label, ok, weight, detail=''):
        signals.append(
            {'code': code, 'label': label, 'ok': bool(ok), 'weight': weight, 'detail': detail}
        )

    body_html = product.description or ''
    body_text = re.sub(r'<[^>]+>', ' ', body_html)
    body_text = re.sub(r'\s+', ' ', body_text).strip()
    words = body_text.split() if body_text else []
    word_count = len(words)

    # 1. Quotable TL;DR / direct answer (the #1 AEO lever). Either an
    #    explicit seo.ai_answer metafield OR a concise short_description
    #    that reads as a standalone answer (15–60 words).
    tldr = ai_answer_for(product)
    short = re.sub(r'<[^>]+>', ' ', product.short_description or '')
    short = re.sub(r'\s+', ' ', short).strip()
    short_words = len(short.split())
    has_answer = bool(tldr) or (15 <= short_words <= 60)
    add(
        'tldr_answer',
        'Has a quotable TL;DR / direct answer',
        has_answer,
        22,
        'AEO answer set' if tldr else (f'{short_words}-word summary' if short else 'none'),
    )
    if not has_answer:
        suggestions.append(
            'Add a 1–2 sentence "key answer" (Site SEO → AI answer, or a tight '
            'short description) that an AI engine can quote verbatim.'
        )

    # 2. FAQ / Q&A schema present — AI engines cite Q&A blocks heavily.
    has_faq = False
    try:
        from django.contrib.contenttypes.models import ContentType
        from plugins.installed.metafields.models import Metafield

        # PDP FAQs live in the seo.pdp_faqs JSON metafield (see the
        # generate_pdp_faqs command); a non-empty list counts.
        ct = ContentType.objects.get_for_model(type(product))
        faq_mf = Metafield.objects.filter(
            content_type=ct,
            object_id=str(product.pk),
            namespace='seo',
            key='pdp_faqs',
        ).first()
        has_faq = bool(faq_mf and faq_mf.value and faq_mf.value.strip() not in ('', '[]'))
    except Exception:  # noqa: BLE001
        has_faq = False
    add(
        'faq_schema',
        'FAQ / Q&A content for schema',
        has_faq,
        14,
        'pdp_faqs present' if has_faq else 'none',
    )
    if not has_faq:
        suggestions.append(
            'Publish 2–3 buyer FAQs — they emit FAQPage/QAPage schema, which AI '
            'engines quote more than any other block.'
        )

    # 3. Clear heading structure — AI extractors chunk on H2/H3.
    heading_count = len(re.findall(r'<h[23]\b', body_html, flags=re.I)) + len(
        re.findall(r'(?m)^\s*#{2,3}\s+\S', body_html)
    )
    headings_ok = heading_count >= 2 or word_count < 120
    add('headings', 'Scannable H2/H3 headings', headings_ok, 12, f'{heading_count} headings')
    if not headings_ok:
        suggestions.append('Break the copy with 2–3 descriptive H2 subheadings so AI can chunk it.')

    # 4. Factual density — quotable numbers/stats (prices, dates, counts,
    #    %, measurements). Pages dense with concrete facts get cited more.
    stat_hits = len(
        re.findall(
            r'\b\d[\d,.]*\s?(?:%|kg|g|cm|mm|pages?|hours?|years?|min)\b', body_text, flags=re.I
        )
    )
    stat_hits += len(re.findall(r'(?<![\w$])\d{3,}', body_text))  # big round numbers
    facts_ok = stat_hits >= 2 or word_count < 120
    add('factual_density', 'Quotable facts / stats', facts_ok, 10, f'{stat_hits} numeric facts')
    if not facts_ok:
        suggestions.append(
            'Add 2+ concrete facts (page count, dimensions, dates, percentages) — '
            'AI engines preferentially cite stat-dense pages.'
        )

    # 5. Freshness — dateModified within 180 days. AI Overviews + Perplexity
    #    decay stale citations fast.
    fresh_ok = False
    detail = 'unknown'
    updated = getattr(product, 'updated_at', None)
    if updated:
        try:
            from django.utils import timezone

            age_days = (timezone.now() - updated).days
            fresh_ok = age_days <= 180
            detail = f'{age_days}d old'
        except Exception:  # noqa: BLE001
            fresh_ok = True
    add('freshness', 'Updated within 180 days (dateModified)', fresh_ok, 10, detail)
    if not fresh_ok:
        suggestions.append('Refresh the page — re-save it so dateModified is recent (<180 days).')

    # 6. E-E-A-T author / entity — a named author or publisher entity.
    has_author = False
    try:
        from plugins.installed.book_product.compat import book_attrs

        book_meta = book_attrs(product)  # model-first, legacy book.* fallback
        has_author = bool(book_meta.get('author') or book_meta.get('publisher'))
    except Exception:  # noqa: BLE001
        has_author = False
    add(
        'eeat_author',
        'Author / publisher entity (E-E-A-T)',
        has_author,
        8,
        'author or publisher set' if has_author else 'none',
    )
    if not has_author:
        suggestions.append('Set the author (and publisher) so JSON-LD carries an E-E-A-T entity.')

    # 7. sameAs entity links — ties the product to a knowledge-graph node.
    has_sameas = False
    try:
        from django.contrib.contenttypes.models import ContentType
        from plugins.installed.metafields.models import Metafield

        ct = ContentType.objects.get_for_model(type(product))
        m = Metafield.objects.filter(
            content_type=ct,
            object_id=str(product.pk),
            namespace='seo',
            key='same_as',
        ).first()
        has_sameas = bool(m and m.value)
    except Exception:  # noqa: BLE001
        has_sameas = False
    add('sameas_entity', 'sameAs entity links', has_sameas, 6, 'linked' if has_sameas else 'none')
    if not has_sameas:
        suggestions.append(
            'Add sameAs links (Wikipedia / Wikidata / Goodreads / official page) via the '
            'seo.same_as metafield to anchor the entity in the knowledge graph.'
        )

    # 8. Enough substance to be worth citing at all.
    substance_ok = word_count >= 120
    add(
        'substance',
        'Enough long-form substance (120+ words)',
        substance_ok,
        8,
        f'{word_count} words',
    )
    if not substance_ok:
        suggestions.append('Expand the body past 120 words — thin pages rarely get cited.')

    earned = sum(s['weight'] for s in signals if s['ok'])
    total = sum(s['weight'] for s in signals) or 1
    score = round(earned / total * 100)
    return {'score': score, 'signals': signals, 'suggestions': suggestions}


def store_audit(product, result: dict) -> 'SeoAuditResult':  # noqa: F821
    from plugins.installed.seo.models import SeoAuditResult
    from django.contrib.contenttypes.models import ContentType

    ct = ContentType.objects.get_for_model(type(product))
    audit, _ = SeoAuditResult.objects.update_or_create(
        content_type=ct,
        object_id=str(product.pk),
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
