"""Agent tools contributed by ai_assistant.

`catalog.semantic_search` exposes the already-built semantic/hybrid retrieval
service (services/search.py) to Linda + the agent layer. It is contributed only
when the `enable_semantic_search` flag is on (Settings → AI) — see
`AIAssistantPlugin.contribute_agent_tools`.
"""

from __future__ import annotations

from core.agents import tool
from core.agents.tools import ToolResult


@tool(
    name='catalog.semantic_search',
    description=(
        'Search the catalog by meaning, not just keywords — ranks products by '
        'semantic similarity (dense embeddings) with a keyword fallback. Prefer '
        'this over catalog.find_products when a shopper describes what they want '
        'in natural language ("a cosy book for winter evenings").'
    ),
    scopes=['catalog.read'],
    schema={
        'type': 'object',
        'properties': {
            'query': {
                'type': 'string',
                'description': 'Natural-language description of what to find.',
            },
            'limit': {'type': 'integer', 'minimum': 1, 'maximum': 25, 'default': 8},
        },
        'required': ['query'],
    },
)
def semantic_search_tool(*, query: str, limit: int = 8) -> ToolResult:
    from plugins.installed.ai_assistant.services.search import semantic_search

    q = (query or '').strip()
    if not q:
        return ToolResult(output={'products': [], 'used_embedding': False})

    try:
        n = max(1, min(int(limit or 8), 25))
    except (TypeError, ValueError):
        n = 8

    products, used_embedding = semantic_search(q, limit=n)
    rows = [
        {
            'slug': p.slug,
            'name': p.name,
            'price': str(getattr(getattr(p, 'price', None), 'amount', '') or ''),
            'category': p.category.name if getattr(p, 'category_id', None) else '',
        }
        for p in products
    ]
    mode = 'semantic' if used_embedding else 'keyword (no embeddings yet)'
    return ToolResult(
        output={'query': q, 'used_embedding': used_embedding, 'products': rows},
        display=f'{len(rows)} result(s) for "{q}" via {mode}.',
    )


@tool(
    name='catalog.classify_product',
    description=(
        'Zero-shot classify a catalog product into candidate labels using the '
        'LLM — no training data. Give a product slug; optionally supply your own '
        'candidate labels, otherwise the store category names are used. Returns '
        'the best-fitting labels (a subset of the candidates). Useful for '
        'suggesting a category/genre for an uncategorised product.'
    ),
    scopes=['catalog.read'],
    schema={
        'type': 'object',
        'properties': {
            'slug': {'type': 'string', 'description': 'Slug of the product to classify.'},
            'labels': {
                'type': 'array',
                'items': {'type': 'string'},
                'description': 'Optional candidate labels; defaults to store categories.',
            },
            'max_labels': {'type': 'integer', 'minimum': 1, 'maximum': 5, 'default': 3},
        },
        'required': ['slug'],
    },
)
def zero_shot_classify_tool(*, slug: str, labels: list | None = None, max_labels: int = 3):
    from plugins.installed.ai_assistant.services.zero_shot import classify_product

    s = (slug or '').strip()
    if not s:
        return ToolResult(output={'labels': [], 'error': 'a product slug is required'})

    from plugins.installed.catalog.models import Product

    product = Product.objects.filter(slug=s).first()
    if product is None:
        return ToolResult(output={'labels': [], 'error': f'no product with slug {s!r}'})

    try:
        n = max(1, min(int(max_labels or 3), 5))
    except (TypeError, ValueError):
        n = 3
    clean_labels = [str(label) for label in labels] if labels else None
    res = classify_product(product, labels=clean_labels, max_labels=n)
    picked = res.get('labels', [])
    return ToolResult(
        output={'slug': s, 'name': product.name, **res},
        display=(
            f'{product.name}: {", ".join(picked)}' if picked else f'{product.name}: no label fit'
        ),
    )
