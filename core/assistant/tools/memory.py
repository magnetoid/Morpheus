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

# A stored fact is included by semantic similarity only above this cosine floor,
# so an unrelated query never floods the result with weakly-related rows. (With
# the hash-fallback embedding, unrelated text scores ~0, so keyword carries.)
_SEMANTIC_FLOOR = 0.25


@tool(
    name='memory.remember',
    description=(
        'Save a fact Linda should recall in future sessions. '
        'Use sparingly — only for stable preferences ("prefers Postmark", '
        '"runs Black Friday in mid-November"), not transient state.'
    ),
    # A write scope — this MUTATES rows. The label matters: run_python's
    # sandbox admits only read-scoped tools, so a 'system.read' tag here let
    # scripts write memory (a real leak, fixed 2026-07).
    scopes=['system.write'],
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
    from core.embeddings import embed

    value = value[:5000]
    obj, created = LindaMemory.objects.update_or_create(
        scope=scope,
        key=key,
        defaults={
            'value': value,
            'source': source[:40],
            # Embed "key: value" so recall can match by meaning, not just
            # substring. Hash-fallback when no provider is configured.
            'embedding': embed(f'{key}: {value}'),
        },
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
    from core.assistant.models import LindaMemory

    qs = LindaMemory.objects.all()
    if scope:
        if scope not in _VALID_SCOPES:
            raise ToolError(f'invalid scope: {scope}')
        qs = qs.filter(scope=scope)

    limit = max(1, min(100, int(limit or 50)))

    if query:
        # Rank by keyword hit + embedding similarity. Substring matches always
        # win (precise); semantic matches above the floor are added so Linda
        # recalls a fact phrased differently from how it was stored. Bounded
        # candidate scan keeps the in-Python sort cheap.
        from core.embeddings import cosine_similarity, embed

        qvec = embed(query)
        ql = query.lower()
        scored: list[tuple[float, object]] = []
        for r in qs[:1000]:
            keyword = 1.0 if (ql in (r.key or '').lower() or ql in (r.value or '').lower()) else 0.0
            semantic = cosine_similarity(qvec, r.embedding) if r.embedding else 0.0
            if keyword or semantic >= _SEMANTIC_FLOOR:
                scored.append((keyword + semantic, r))
        scored.sort(key=lambda t: t[0], reverse=True)
        result_rows = [r for _, r in scored[:limit]]
    else:
        result_rows = list(qs[:limit])

    rows = [
        {
            'scope': r.scope,
            'key': r.key,
            'value': r.value,
            'source': r.source,
            'updated_at': r.updated_at.isoformat(),
        }
        for r in result_rows
    ]
    return ToolResult(output={'memories': rows, 'count': len(rows)})


@tool(
    name='memory.forget',
    description='Delete a remembered fact by (scope, key).',
    scopes=['system.write'],  # deletes rows — see memory.remember's scope note
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


def get_recent_memories(limit: int = 50, *, query: str = '') -> list[dict]:
    """Top-of-turn injection helper — returns ``[{scope, key, value}, ...]``
    for the most relevant memories by combined source-confidence + temporal
    decay. The May-2026 industry consensus (Mem0 / Zep) is that flat recency
    misses the "user told me a key preference six weeks ago" fact in favour
    of yesterday's noise — relevance scoring fixes that.

    When ``query`` is given (the merchant's current message), rows whose
    embedding clears ``_SEMANTIC_FLOOR`` get the cosine similarity ADDED to
    their decay score — so what the merchant is asking about right now
    outranks merely-recent facts. Rows without embeddings keep decay-only.

    Fails closed: when the table doesn't exist or the import fails, returns
    an empty list so Linda still works on a fresh install.
    """
    try:
        from core.assistant.models import LindaMemory

        # Cap the query at 4× the desired output so the in-Python sort stays
        # bounded even on databases with thousands of rows.
        candidates = list(LindaMemory.objects.all()[: max(limit * 4, 200)])
        qvec = None
        if (query or '').strip():
            try:
                from core.embeddings import embed

                qvec = embed(query.strip()[:2000])
            except Exception:  # noqa: BLE001 — embedding outage → decay-only
                qvec = None

        def _score(r) -> float:
            try:
                s = r.relevance_score()
            except Exception:  # noqa: BLE001
                s = 0.0
            if qvec is not None and r.embedding:
                try:
                    from core.embeddings import cosine_similarity

                    sem = cosine_similarity(qvec, r.embedding)
                    if sem >= _SEMANTIC_FLOOR:
                        s += sem
                except Exception:  # noqa: BLE001, S110 — malformed vector → decay-only
                    pass
            return s

        candidates.sort(key=_score, reverse=True)
        return [{'scope': r.scope, 'key': r.key, 'value': r.value} for r in candidates[:limit]]
    except Exception:  # noqa: BLE001
        return []
