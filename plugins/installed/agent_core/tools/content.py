"""Content tools — drafting product copy via the LLM gateway."""

from __future__ import annotations

import logging

from core.agents import get_llm_provider
from core.agents.llm import LLMMessage
from morpheus.core import ToolError, ToolResult, tool

logger = logging.getLogger('morpheus.agents.content')


@tool(
    name='content.draft_product_description',
    description='Generate a 60–120 word product description for a product (by slug).',
    scopes=['content.write'],
    schema={
        'type': 'object',
        'properties': {
            'slug': {'type': 'string'},
            'tone': {
                'type': 'string',
                'enum': ['neutral', 'literary', 'witty', 'minimal'],
                'default': 'literary',
            },
        },
        'required': ['slug'],
    },
    requires_approval=True,  # writes are approval-gated by default
)
def draft_product_description_tool(*, slug: str, tone: str = 'literary') -> ToolResult:
    from plugins.installed.catalog.models import Product

    try:
        p = Product.objects.get(slug=slug)
    except Product.DoesNotExist as e:
        raise ToolError(f'Unknown product: {slug}') from e

    provider = get_llm_provider()
    msgs = [
        LLMMessage(
            role='system',
            content=(
                f'You are a {tone} bookshop copywriter. Write a 60–120 word product '
                'description. Avoid spoilers, hype, and generic adjectives.'
            ),
        ),
        LLMMessage(
            role='user',
            content=(
                f'Product: {p.name}\n'
                f'Category: {p.category.name if p.category_id else ""}\n'
                f'Existing short: {p.short_description or ""}\n'
                f'Existing long: {(p.description or "")[:1200]}'
            ),
        ),
    ]
    resp = provider.respond(messages=msgs, tools=None, temperature=0.6, max_tokens=400)
    return ToolResult(
        output={'product_slug': slug, 'draft': resp.text},
        display=f'Draft for {p.name}',
        metadata={'tokens_in': resp.prompt_tokens, 'tokens_out': resp.completion_tokens},
    )


@tool(
    name='catalog.fill_missing_content',
    description=(
        'Fill missing short_description / description / category for products '
        'that have any of those fields empty. Only writes to fields that are '
        'actually blank — idempotent on already-populated rows. Picks an '
        'existing category by name match (never auto-creates new categories). '
        'Use `limit` to cap how many products are processed per call; pass '
        '`slug` to target a single product instead.'
    ),
    scopes=['catalog.read', 'catalog.write', 'content.write'],
    schema={
        'type': 'object',
        'properties': {
            'slug': {
                'type': 'string',
                'description': 'Optional. If set, only fill this product. Otherwise process up to `limit` incomplete products.',
            },
            'limit': {
                'type': 'integer',
                'minimum': 1,
                'maximum': 50,
                'default': 10,
                'description': 'Max products to process in this call when slug is not provided.',
            },
            'tone': {
                'type': 'string',
                'enum': ['neutral', 'literary', 'witty', 'minimal'],
                'default': 'literary',
            },
        },
    },
    requires_approval=True,
)
def fill_missing_content_tool(  # noqa: PLR0912
    *, slug: str = '', limit: int = 10, tone: str = 'literary'
) -> ToolResult:  # noqa: PLR0912
    from django.db.models import Q

    from plugins.installed.catalog.models import Category, Product

    limit = max(1, min(int(limit or 10), 50))
    provider = get_llm_provider()

    if slug:
        qs = Product.objects.filter(slug=slug)
    else:
        qs = (
            Product.objects.filter(
                Q(short_description='') | Q(description='') | Q(category__isnull=True),
            )
            .select_related('category')
            .order_by('status', 'name')[:limit]
        )

    cat_names = list(Category.objects.values_list('name', flat=True)[:200])

    processed = []
    for p in qs:
        updated_fields = []

        # 1) short description
        if not (p.short_description or '').strip():
            try:
                resp = provider.respond(
                    messages=[
                        LLMMessage(
                            role='system',
                            content=(
                                f'You are a {tone} bookstore copywriter. Write a '
                                'single sentence (12–25 words) summarising the book. '
                                'No hype, no spoilers, no marketing adjectives.'
                            ),
                        ),
                        LLMMessage(
                            role='user',
                            content=(
                                f'Title: {p.name}\n'
                                f'Existing long description: {(p.description or "")[:600]}'
                            ),
                        ),
                    ],
                    tools=None,
                    temperature=0.5,
                    max_tokens=120,
                )
                short = (resp.text or '').strip().strip('"').strip()
                if short:
                    p.short_description = short[:600]
                    updated_fields.append('short_description')
            except Exception as e:  # noqa: BLE001
                logger.warning('fill_missing_content: short failed for %s: %s', p.slug, e)

        # 2) long description
        if not (p.description or '').strip():
            try:
                resp = provider.respond(
                    messages=[
                        LLMMessage(
                            role='system',
                            content=(
                                f'You are a {tone} bookstore copywriter. Write an '
                                '80–140 word product description. Plain prose, short '
                                'sentences. No spoilers, no hype, no generic adjectives.'
                            ),
                        ),
                        LLMMessage(
                            role='user',
                            content=(
                                f'Title: {p.name}\n'
                                f'Category: {p.category.name if p.category_id else "—"}\n'
                                f'Existing short: {p.short_description or ""}'
                            ),
                        ),
                    ],
                    tools=None,
                    temperature=0.6,
                    max_tokens=400,
                )
                long_desc = (resp.text or '').strip()
                if long_desc:
                    p.description = long_desc[:5000]
                    updated_fields.append('description')
            except Exception as e:  # noqa: BLE001
                logger.warning('fill_missing_content: long failed for %s: %s', p.slug, e)

        # 3) category match against existing catalog (no auto-create)
        if p.category_id is None and cat_names:
            try:
                resp = provider.respond(
                    messages=[
                        LLMMessage(
                            role='system',
                            content=(
                                'Pick the SINGLE best-fit category for this book '
                                'from the list. Reply with EXACTLY the category name. '
                                'If none fit well, reply NONE.'
                            ),
                        ),
                        LLMMessage(
                            role='user',
                            content=(
                                f'Title: {p.name}\n'
                                f'Description: {(p.description or p.short_description or "")[:600]}\n\n'
                                f'Categories:\n- ' + '\n- '.join(cat_names)
                            ),
                        ),
                    ],
                    tools=None,
                    temperature=0.1,
                    max_tokens=40,
                )
                guess = (resp.text or '').strip().strip('"').strip()
                if guess and guess.upper() != 'NONE':
                    cat = Category.objects.filter(name__iexact=guess).first()
                    if cat:
                        p.category = cat
                        updated_fields.append('category')
            except Exception as e:  # noqa: BLE001
                logger.warning('fill_missing_content: category failed for %s: %s', p.slug, e)

        if updated_fields:
            save_fields = list(updated_fields)
            save_fields.append('updated_at')
            p.save(update_fields=save_fields)

        processed.append(
            {
                'slug': p.slug,
                'name': p.name,
                'updated': updated_fields,
            }
        )

    filled = sum(1 for r in processed if r['updated'])
    return ToolResult(
        output={
            'processed_count': len(processed),
            'filled_count': filled,
            'products': processed,
        },
        display=f'filled {filled}/{len(processed)} product(s)',
    )
