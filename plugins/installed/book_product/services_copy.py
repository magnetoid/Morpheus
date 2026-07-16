"""AI copy generation for book-taxonomy pages.

One prompt builder + one LLM call, shared by the dashboard's per-page
"Generate" button (``dashboard_taxonomies.taxonomy_generate``) and the bulk
backfill task (``tasks.backfill_taxonomy_copy``) — so both write in the same
house voice and the prompt has exactly one place to be tuned.
"""

# ruff: noqa: PLC0415
from __future__ import annotations

# Curated kinds are real models (Genre/Topic); the rest derive from BookProduct
# string fields. Kept local so this module doesn't import the dashboard.
_CURATED_LABELS = {'genre': 'Genre', 'topic': 'Topic'}
_DERIVED_LABELS = {
    'author': 'Authors',
    'publisher': 'Publishers',
    'series': 'Series',
    'imprint': 'Imprints',
}


class CopyGenerationError(RuntimeError):
    """The AI provider was unavailable or misconfigured."""


def _curated_model(kind):
    from plugins.installed.book_product.models import Genre, Topic

    return {'genre': Genre, 'topic': Topic}.get(kind)


def _subject_for(taxonomy: str, slug: str) -> tuple[str, str]:
    """Return ``(subject, context_line)`` describing the page being written.

    `subject` names the page for the prompt; `context_line` grounds it in real
    catalog data (the books actually on it) so the model writes something
    specific instead of generic filler. Raises LookupError for an unknown
    taxonomy or term.
    """
    from plugins.installed.book_product.compat import (
        distinct_values,
        product_ids_for,
        resolve_slug,
    )
    from plugins.installed.catalog.models import Product

    if taxonomy in _CURATED_LABELS:
        label = _CURATED_LABELS[taxonomy]
        model = _curated_model(taxonomy)
        if slug:
            obj = model.objects.filter(slug=slug).first()
            if obj is None:
                raise LookupError('Unknown term.')
            titles = [t for t in obj.books.values_list('product__name', flat=True)[:12] if t]
            return (
                f'the {label} page for "{obj.name}"',
                f'Books on this page: {", ".join(titles) or "(none yet)"}.',
            )
        terms = list(model.objects.values_list('name', flat=True)[:15])
        return (
            f'the {label} index page, which lists every {label.lower()}',
            f'{label}s include: {", ".join(terms) or "(none yet)"}.',
        )

    if taxonomy not in _DERIVED_LABELS:
        raise LookupError('Unknown taxonomy.')
    label = _DERIVED_LABELS[taxonomy]
    if slug:
        name = resolve_slug(taxonomy, slug) or slug
        ids = product_ids_for(taxonomy, name)[:12]
        titles = list(Product.objects.filter(id__in=ids).values_list('name', flat=True)[:12])
        return (
            f'the {label} page for "{name}"',
            f'Books on this page: {", ".join(titles) or "(none yet)"}.',
        )
    terms = distinct_values(taxonomy)[:15]
    return (
        f'the {label} index page, which lists every {label.lower()} entry',
        f'{label} include: {", ".join(terms) or "(none yet)"}.',
    )


def build_prompt(
    subject: str, context_line: str, *, mode: str = 'generate', existing: str = ''
) -> str:
    if mode == 'rewrite' and existing:
        # Rewrite just the intro the merchant already has — keep their facts,
        # improve the prose. Returns only {description}.
        return (
            f'Rewrite and improve this intro for {subject} on dot books, an '
            'independent online bookshop. Keep it warm, concise (2-3 sentences) '
            'and specific; preserve the facts. Return STRICT JSON {"description": '
            '"..."} and nothing else.\n\nCurrent text:\n' + existing
        )
    return (
        f'Write storefront copy for {subject} on an independent online bookshop '
        f'called dot books.\n{context_line}\n\n'
        'Return STRICT JSON (no markdown, nothing outside the JSON) with keys:\n'
        '  "description": a warm, specific 2-3 sentence editorial intro (plain text),\n'
        '  "meta_title": an SEO title, max 60 characters,\n'
        '  "meta_description": an SEO meta description, max 155 characters.'
    )


def generate_copy(
    taxonomy: str, slug: str = '', *, mode: str = 'generate', existing: str = ''
) -> dict:
    """Generate ``{description, meta_title, meta_description}`` for one page.

    Raises LookupError for an unknown taxonomy/term and CopyGenerationError
    when the provider is missing or errors — callers decide whether that's a
    JSON error payload (dashboard) or a skipped row (bulk backfill).
    """
    from core.llm_parsing import parse_llm_json

    subject, context_line = _subject_for(taxonomy, slug)
    prompt = build_prompt(subject, context_line, mode=mode, existing=existing)
    try:
        from plugins.installed.ai_assistant.services.llm import get_llm

        raw = get_llm().complete(
            prompt,
            system='You write concise, warm, specific bookshop copy. Output JSON only.',
            max_tokens=400,
            temperature=0.7,
        )
    except Exception as e:  # noqa: BLE001 — provider missing/misconfigured
        raise CopyGenerationError(str(e)) from e

    data = parse_llm_json(raw) if raw else None
    if not isinstance(data, dict):
        data = {'description': (raw or '').strip()[:600]}
    return {
        'description': (data.get('description') or '').strip()[:600],
        'meta_title': (data.get('meta_title') or '').strip()[:200],
        'meta_description': (data.get('meta_description') or '').strip()[:320],
    }
