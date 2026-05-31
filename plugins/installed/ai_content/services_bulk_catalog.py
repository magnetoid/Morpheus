"""Bulk catalog AI operations — rewrite / translate / expand product copy.

Three operations, all callable from the admin Products list page:
  - rewrite(target='description'|'meta_description'|'short_description',
            tone, products) — rewrites in shop voice + new tone.
  - translate(target, language, products) — i18n via the i18n kernel.
  - expand(target, products) — extend a stub description into 3-4
    paragraphs of merchant-quality copy.

Implementation:
  - Wraps the LLM provider already used by ai_content (Anthropic via
    core.assistant.providers).
  - Brand voice (services.get_brand_voice + with_brand_voice) is applied
    automatically.
  - Writes are gated by a `dry_run` flag — admin can preview before
    committing.

Cost model: each operation is one ~600-token completion per product.
~$0.004 per product on Sonnet 4.x. A 1000-product bulk pass = ~$4.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from plugins.installed.ai_content.services import with_brand_voice

logger = logging.getLogger('morpheus.ai_content.bulk_catalog')

VALID_TARGETS = ('description', 'meta_description', 'short_description', 'name')
TONE_LIBRARY = {
    'editorial': 'Editorial, literary, evocative.',
    'concise': 'Short, punchy, scannable.',
    'enthusiastic': 'Energetic, customer-facing, warm.',
    'technical': 'Precise, specification-led, no fluff.',
    'persuasive': 'Conversion-optimised, benefit-led, clear CTAs.',
}


@dataclass(slots=True)
class CatalogOpResult:
    product_id: str
    old_value: str
    new_value: str
    applied: bool = False
    error: str = ''
    tokens_used: int = 0


@dataclass(slots=True)
class BulkRunResult:
    results: list = field(default_factory=list)
    total_tokens: int = 0
    failed: int = 0
    succeeded: int = 0


def rewrite(
    *,
    target: str,
    tone: str,
    product_ids: list,
    dry_run: bool = True,
) -> BulkRunResult:
    """Rewrite `target` on each product in the new `tone`."""
    if target not in VALID_TARGETS:
        raise ValueError(f'unknown target {target!r}')
    tone_directive = TONE_LIBRARY.get(tone, tone)

    def op(p: Any, current: str) -> tuple[str, int]:
        prompt = (
            f'Rewrite this product {target} for the storefront. '
            f'Tone: {tone_directive}\n\n'
            f'Product name: {getattr(p, "name", "")}\n'
            f'Current {target}: {current}\n\n'
            f'Output only the rewritten {target}. No preamble, no labels.'
        )
        return _call_llm(prompt)

    return _bulk_run(target=target, product_ids=product_ids, op=op, dry_run=dry_run)


def translate(
    *,
    target: str,
    language: str,
    product_ids: list,
    dry_run: bool = True,
) -> BulkRunResult:
    """Translate `target` into `language` (e.g. 'fr', 'es', 'de').

    Phase 1 writes the translation directly onto the field — Phase 2
    will write into the i18n Translation table so the original survives.
    Until then, use dry_run=True to preview before committing.
    """
    if target not in VALID_TARGETS:
        raise ValueError(f'unknown target {target!r}')

    def op(p: Any, current: str) -> tuple[str, int]:
        prompt = (
            f'Translate this product {target} into {language}.\n'
            f"Keep tone + register. Don't add notes or explanations.\n\n"
            f'Source: {current}\n\n'
            f'Output only the translation.'
        )
        return _call_llm(prompt)

    return _bulk_run(target=target, product_ids=product_ids, op=op, dry_run=dry_run)


def expand(
    *,
    target: str,
    product_ids: list,
    dry_run: bool = True,
) -> BulkRunResult:
    """Expand a stub into 3-4 paragraphs of merchant-quality copy."""
    if target not in VALID_TARGETS:
        raise ValueError(f'unknown target {target!r}')

    def op(p: Any, current: str) -> tuple[str, int]:
        category = getattr(getattr(p, 'category', None), 'name', '')
        prompt = (
            f'Expand this product {target} into 3-4 paragraphs of customer-facing copy.\n'
            f'Product: {getattr(p, "name", "")}\n'
            f'Category: {category or "general"}\n'
            f'Current copy: {current or "(none)"}\n\n'
            f"Cover: what it is, who it's for, why someone would buy it.\n"
            f'No marketing fluff, no superlatives without specifics.\n'
            f'Output the new {target} only.'
        )
        return _call_llm(prompt)

    return _bulk_run(target=target, product_ids=product_ids, op=op, dry_run=dry_run)


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _bulk_run(
    *,
    target: str,
    product_ids: list,
    op,
    dry_run: bool,
) -> BulkRunResult:
    from plugins.installed.catalog.models import Product  # noqa: PLC0415

    result = BulkRunResult()
    products = Product.objects.filter(pk__in=product_ids)
    for product in products:
        current = getattr(product, target, '') or ''
        try:
            new_value, tokens = op(product, current)
            result.total_tokens += tokens
            entry = CatalogOpResult(
                product_id=str(product.pk),
                old_value=current,
                new_value=new_value,
                tokens_used=tokens,
            )
            if not dry_run and new_value and new_value.strip() != current.strip():
                setattr(product, target, new_value.strip())
                product.save(update_fields=[target])
                entry.applied = True
                result.succeeded += 1
            elif dry_run:
                entry.applied = False
            result.results.append(entry)
        except Exception as exc:  # noqa: BLE001
            logger.exception('ai_content.bulk: %s failed for product=%s', target, product.pk)
            result.failed += 1
            result.results.append(
                CatalogOpResult(
                    product_id=str(product.pk),
                    old_value=current,
                    new_value='',
                    error=str(exc)[:300],
                )
            )
    return result


def _call_llm(user_prompt: str) -> tuple[str, int]:
    """Call the LLM with brand-voice context. Returns (text, tokens_used).

    Resolves the provider lazily so dev environments without an API key
    can run the catalog views without import-time errors.
    """
    from core.assistant.providers import get_default_provider  # noqa: PLC0415

    provider = get_default_provider()
    if provider is None:
        raise RuntimeError('No LLM provider configured (set ANTHROPIC_API_KEY or similar).')

    system = with_brand_voice('You are an expert e-commerce copywriter for this shop.')
    response = provider.complete(
        system=system,
        messages=[{'role': 'user', 'content': user_prompt}],
        max_tokens=1200,
        temperature=0.5,
    )
    text = (response.get('text') or '').strip()
    tokens = int(response.get('usage', {}).get('total_tokens', 0))
    return text, tokens
