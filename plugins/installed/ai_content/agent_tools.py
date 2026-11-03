"""Linda's view of which product text an AI wrote.

Read only, on purpose: a mark exists because an agent wrote the text, so no agent
can remove one. The merchant clears it in the product editor's "Written with AI"
card.
"""

from __future__ import annotations

from morpheus.core import ToolError, ToolResult, tool


@tool(
    name='products.ai_written',
    description=(
        "Which of a product's texts are marked as written with AI (description, "
        'short description, meta title, meta description) and who wrote each: Linda, '
        "an AI worker, the product editor's AI writer, or a bulk rewrite. A marked "
        'description is said on the product page and in its structured data. Pass '
        '`id`, `sku` or `slug`. Only the merchant can clear a mark, in the product '
        'editor.'
    ),
    scopes=['catalog.read'],
    schema={
        'type': 'object',
        'properties': {
            'id': {'type': 'string'},
            'sku': {'type': 'string'},
            'slug': {'type': 'string'},
        },
    },
)
def products_ai_written_tool(*, id: str = '', sku: str = '', slug: str = '') -> ToolResult:
    from plugins.installed.ai_content.marks import SOURCES, marks_for
    from plugins.installed.catalog.models import Product

    product = (
        (id and Product.objects.filter(pk=id).first())
        or (sku and Product.objects.filter(sku=sku).first())
        or (slug and Product.objects.filter(slug=slug).first())
        or None
    )
    if product is None:
        raise ToolError('not found — pass id, sku or slug')
    marked = marks_for(product)
    fields = {field: SOURCES.get(source, source) for field, source in sorted(marked.items())}
    return ToolResult(
        output={'product': product.slug, 'ai_written': fields},
        display=(
            f'{product.name}: written with AI — {", ".join(fields)}'
            if fields
            else f'{product.name}: no text marked as written with AI'
        ),
    )
