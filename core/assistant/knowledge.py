"""Knowledge-retriever seam for Linda's RAG.

Core owns the *interface*; a plugin (``ai_assistant``) registers the actual
retriever in its ``ready()`` — exactly like the LLM provider-config resolver
(``core/agents/provider_registry.py``). This keeps the wrong-direction import
out of core: the plugin pushes its retriever in, core never imports the plugin.

Disable-safe by construction. On a cold boot with ai_assistant off, ``ready()``
never runs so no retriever is registered; on a runtime toggle the retriever is
left registered but simply keeps returning ``[]`` once its rows are gone — RAG
is strictly additive, never a hard dependency of the agent loop. See
``docs/plans/rag-knowledge-base.md``.
"""

from __future__ import annotations

from collections.abc import Callable

# (query, k) -> [{'source': str, 'ref': str, 'title': str, 'text': str}, ...]
Retriever = Callable[[str, int], list[dict]]

# Single-slot registry (a dict avoids the discouraged ``global`` rebind).
_STATE: dict[str, Retriever | None] = {'retriever': None}


def register_retriever(fn: Retriever) -> None:
    """Install the knowledge retriever. Called once from ai_assistant.ready()."""
    _STATE['retriever'] = fn


def retrieve(query: str, k: int = 4) -> list[dict]:
    """Return up to ``k`` knowledge chunks relevant to ``query``.

    Empty list when no retriever is registered, the query is blank, or anything
    goes wrong — retrieval must never break the chat loop.
    """
    fn = _STATE['retriever']
    if fn is None or not query or not query.strip():
        return []
    try:
        return fn(query, k) or []
    except Exception:  # noqa: BLE001 — RAG is additive; never fail the turn
        return []
