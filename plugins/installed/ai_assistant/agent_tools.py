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
