"""Embedding service — promoted to core in PR11.

Resolves an embedding provider based on `settings.AI_PROVIDER` and
`settings.AI_EMBEDDING_MODEL`. Always returns a fixed-dimension list of
floats so the rest of the system never has to know which backend was used.

When no provider is configured (CI, local dev with no keys), falls back
to a deterministic hash-based embedding so the rest of the pipeline
still works. This is INTENTIONAL — callers can test the full retrieval
flow without paying for tokens. A caller that keeps vectors goes through
``embed_comparable``, so a store with a provider never keeps a hash vector.

Lives in `core` (not `ai_assistant`) because agent-layer code, semantic
search, RAG, and recommendations all need it independently of the AI
Signals plugin being installed.
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Sequence

from django.conf import settings

logger = logging.getLogger('morpheus.embeddings')

EMBEDDING_DIM = 384


def _hash_embedding(text: str) -> list[float]:
    h = hashlib.sha512(text.encode('utf-8')).digest()
    raw = (h * ((EMBEDDING_DIM + len(h) - 1) // len(h)))[:EMBEDDING_DIM]
    return [(b - 128) / 128.0 for b in raw]


def _api_key() -> str:
    """The OpenAI key embeddings are made with, or '' for none.

    The environment's key, while the environment names OpenAI as the provider.
    The key a merchant saved under Settings → AI is used only once they switch
    that on (ai_assistant answers ``EMBEDDINGS_API_KEY``), because it starts
    provider spend. Until v0.200.0 the store's key was looked up through a
    registry method that does not exist, so it was never used.
    """
    provider = getattr(settings, 'AI_PROVIDER', 'openai')
    key = (getattr(settings, 'OPENAI_API_KEY', '') or '') if provider == 'openai' else ''
    try:
        from core.hooks import MorpheusEvents, hook_registry

        answer = hook_registry.filter(MorpheusEvents.EMBEDDINGS_API_KEY, key)
    except Exception:  # noqa: BLE001 — the bus must never cost a turn its recall
        return key
    return answer if isinstance(answer, str) else key


def provider_embedding(text: str) -> list[float] | None:
    """The provider's vector for ``text``. None when there is no key, AI is
    switched off, or the call failed."""
    text = (text or '').strip()
    api_key = _api_key()
    if not text or not api_key:
        return None
    from core.agents.guardrails import agents_paused

    if agents_paused():
        return None
    model = getattr(settings, 'AI_EMBEDDING_MODEL', 'text-embedding-3-small')
    try:
        from openai import OpenAI

        # Bound the request-path cost: this runs inline on chat/RAG/recall
        # turns, and the SDK default (600s timeout + 2 retries) can stall a
        # turn far past the 30s worker budget when the endpoint hangs
        # (audit H3).
        client = OpenAI(api_key=api_key, timeout=10.0, max_retries=0)
        # Pin the output dimension so the OpenAI path honours the module's
        # fixed-dimension contract (text-embedding-3-* default to 1536).
        resp = client.embeddings.create(model=model, input=text, dimensions=EMBEDDING_DIM)
        vec = list(resp.data[0].embedding)
        if len(vec) == EMBEDDING_DIM:
            return vec
        logger.warning('OpenAI embed returned %d dims (expected %d)', len(vec), EMBEDDING_DIM)
    except Exception as e:  # noqa: BLE001
        logger.warning('OpenAI embed failed (%s)', e)
    return None


def embed(text: str) -> list[float]:
    """A vector for ``text``, always: the provider's, else the hash vector
    (no provider, AI switched off, a failed call). To keep a vector, or to rank
    kept ones, use ``embed_comparable``."""
    text = (text or '').strip()
    if not text:
        return [0.0] * EMBEDDING_DIM
    vec = provider_embedding(text)
    return vec if vec is not None else _hash_embedding(text)


def embed_comparable(text: str) -> list[float] | None:
    """A vector to keep, or to rank the kept ones with; None for "not now".

    A store with a provider keeps the provider's vectors, and a hash vector
    among them matches nothing by meaning, for good. So while the provider
    cannot answer (an outage, AI switched off) the caller gets None: it stores
    no vector, and ranks by keyword alone. A store with no provider keeps hash
    vectors throughout.
    """
    text = (text or '').strip()
    if not text:
        return None
    if _api_key():
        return provider_embedding(text)
    return _hash_embedding(text)


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    import math

    # Vectors of different lengths are not comparable — a stored embedding from
    # one backend (e.g. 384-dim hash) vs a query embedding from another
    # (e.g. 1536-dim OpenAI) would otherwise produce a silently garbage score.
    if len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)
