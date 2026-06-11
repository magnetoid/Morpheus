"""Linda's memory tools — remember, recall, forget.

The `memory.remember` tool writes a (scope, key, value) row. `memory.recall`
returns matching rows; absent a query, returns the most-recently-updated
50 entries. `memory.forget` deletes by key.

Reads happen automatically at the top of every Linda turn (see
runtime._inject_memory) — these tools are mostly for explicit writes
and merchant-driven recall.
"""

from __future__ import annotations

# Reuse the @tool decorator + ToolResult shape from filesystem.py — same
# fallback path Linda's other tools take so a kernel-import failure doesn't
# break tool registration.
from core.assistant.tools.filesystem import ToolError, ToolResult, tool

_VALID_SCOPES = ('merchant', 'customer-segment', 'seasonal')


@tool(
    name='memory.remember',
    description=(
        'Save a fact Linda should recall in future sessions. '
        'Use sparingly — only for stable preferences ("prefers Postmark", '
        '"runs Black Friday in mid-November"), not transient state.'
    ),
    scopes=['system.read'],
    schema={
        'type': 'object',
        'properties': {
            'key': {'type': 'string', 'description': 'Short identifier, snake-case if possible.'},
            'value': {'type': 'string', 'description': 'The fact to remember.'},
            'scope': {
                'type': 'string',
                'enum': list(_VALID_SCOPES),
                'default': 'merchant',
            },
            'source': {'type': 'string', 'description': "Optional source tag, e.g. 'user-told'."},
        },
        'required': ['key', 'value'],
    },
)
def memory_remember_tool(
    *, key: str, value: str, scope: str = 'merchant', source: str = 'user-told'
) -> ToolResult:
    if scope not in _VALID_SCOPES:
        raise ToolError(f'invalid scope: {scope}')
    key = (key or '').strip()
    value = (value or '').strip()
    if not key or not value:
        raise ToolError('key and value are both required')
    from core.assistant.models import LindaMemory

    obj, created = LindaMemory.objects.update_or_create(
        scope=scope,
        key=key,
        defaults={'value': value[:5000], 'source': source[:40]},
    )
    return ToolResult(
        output={
            'remembered': True,
            'created': created,
            'scope': obj.scope,
            'key': obj.key,
            'value': obj.value,
        }
    )


@tool(
    name='memory.recall',
    description=(
        'Read remembered facts. Pass `query` to substring-filter on key or value, '
        'or omit to get the 50 most-recently-updated entries.'
    ),
    scopes=['system.read'],
    schema={
        'type': 'object',
        'properties': {
            'query': {'type': 'string', 'description': 'Substring filter (case-insensitive).'},
            'scope': {'type': 'string', 'enum': list(_VALID_SCOPES)},
            'limit': {'type': 'integer', 'minimum': 1, 'maximum': 100, 'default': 50},
        },
    },
)
def memory_recall_tool(*, query: str = '', scope: str = '', limit: int = 50) -> ToolResult:
    from django.db.models import Q

    from core.assistant.models import LindaMemory

    qs = LindaMemory.objects.all()
    if scope:
        if scope not in _VALID_SCOPES:
            raise ToolError(f'invalid scope: {scope}')
        qs = qs.filter(scope=scope)
    if query:
        qs = qs.filter(Q(key__icontains=query) | Q(value__icontains=query))
    rows = [
        {
            'scope': r.scope,
            'key': r.key,
            'value': r.value,
            'source': r.source,
            'updated_at': r.updated_at.isoformat(),
        }
        for r in qs[: max(1, min(100, int(limit or 50)))]
    ]
    return ToolResult(output={'memories': rows, 'count': len(rows)})


@tool(
    name='memory.forget',
    description='Delete a remembered fact by (scope, key).',
    scopes=['system.read'],
    schema={
        'type': 'object',
        'properties': {
            'key': {'type': 'string'},
            'scope': {'type': 'string', 'enum': list(_VALID_SCOPES), 'default': 'merchant'},
        },
        'required': ['key'],
    },
)
def memory_forget_tool(*, key: str, scope: str = 'merchant') -> ToolResult:
    if scope not in _VALID_SCOPES:
        raise ToolError(f'invalid scope: {scope}')
    from core.assistant.models import LindaMemory

    deleted, _ = LindaMemory.objects.filter(scope=scope, key=(key or '').strip()).delete()
    return ToolResult(output={'forgot': deleted > 0, 'scope': scope, 'key': key})


def get_recent_memories(limit: int = 50) -> list[dict]:
    """Top-of-turn injection helper — returns ``[{scope, key, value}, ...]``
    for the most relevant memories by combined source-confidence + temporal
    decay. The May-2026 industry consensus (Mem0 / Zep) is that flat recency
    misses the "user told me a key preference six weeks ago" fact in favour
    of yesterday's noise — relevance scoring fixes that.

    Fails closed: when the table doesn't exist or the import fails, returns
    an empty list so Linda still works on a fresh install.
    """
    try:
        from core.assistant.models import LindaMemory

        # Cap the query at 4× the desired output so the in-Python sort stays
        # bounded even on databases with thousands of rows.
        candidates = list(LindaMemory.objects.all()[: max(limit * 4, 200)])
        candidates.sort(key=lambda r: r.relevance_score(), reverse=True)
        return [{'scope': r.scope, 'key': r.key, 'value': r.value} for r in candidates[:limit]]
    except Exception:  # noqa: BLE001
        return []
