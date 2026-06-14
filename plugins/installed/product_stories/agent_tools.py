"""Agent commands for product stories — Linda can read + author story blocks."""

from __future__ import annotations

from core.agents import tool
from core.agents.tools import ToolResult


@tool(
    name='stories.list_blocks',
    description='List the story blocks on a product (by slug), in display order.',
    scopes=['catalog.read'],
    schema={
        'type': 'object',
        'properties': {'slug': {'type': 'string'}},
        'required': ['slug'],
    },
)
def stories_list_blocks_tool(*, slug: str) -> ToolResult:
    from plugins.installed.product_stories.models import ProductStoryBlock

    blocks = ProductStoryBlock.objects.filter(product__slug=slug).order_by('order')
    rows = [
        {
            'id': str(b.id),
            'order': b.order,
            'eyebrow': b.eyebrow,
            'heading': b.heading,
            'layout': b.layout,
            'active': b.is_active,
        }
        for b in blocks
    ]
    return ToolResult(
        output={'slug': slug, 'blocks': rows, 'count': len(rows)},
        display=f'{len(rows)} story block(s).',
    )


@tool(
    name='stories.add_block',
    description=(
        'Add a "why you\'ll love it" story block to a product page (by slug). '
        'layout: image_right|image_left|image_full|text. Appended to the end.'
    ),
    scopes=['catalog.write'],
    schema={
        'type': 'object',
        'properties': {
            'slug': {'type': 'string'},
            'heading': {'type': 'string'},
            'body': {'type': 'string'},
            'eyebrow': {'type': 'string'},
            'image_url': {'type': 'string'},
            'layout': {'type': 'string'},
        },
        'required': ['slug', 'heading'],
    },
)
def stories_add_block_tool(
    *,
    slug: str,
    heading: str,
    body: str = '',
    eyebrow: str = '',
    image_url: str = '',
    layout: str = 'image_right',
) -> ToolResult:
    from plugins.installed.catalog.models import Product
    from plugins.installed.product_stories.models import ProductStoryBlock

    product = Product.objects.filter(slug=slug).first()
    if product is None:
        return ToolResult(output={'error': f'no product with slug {slug!r}'})
    if not (heading or '').strip():
        return ToolResult(output={'error': 'heading is required'})
    valid = {c[0] for c in ProductStoryBlock.LAYOUT_CHOICES}
    if layout not in valid:
        layout = 'image_right'
    order = ProductStoryBlock.objects.filter(product=product).count()
    block = ProductStoryBlock.objects.create(
        product=product,
        order=order,
        heading=heading.strip()[:200],
        body=(body or '').strip(),
        eyebrow=(eyebrow or '').strip()[:60],
        image_url=(image_url or '').strip()[:500],
        layout=layout,
    )
    return ToolResult(
        output={'id': str(block.id), 'slug': slug, 'order': order},
        display=f'Added story block “{block.heading}” to {slug}.',
    )
