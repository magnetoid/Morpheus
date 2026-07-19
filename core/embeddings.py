"""Embedding service — promoted to core in PR11.

Resolves an embedding provider based on `settings.AI_PROVIDER` and
`settings.AI_EMBEDDING_MODEL`. Always returns a fixed-dimension list of
floats so the rest of the system never has to know which backend was used.

When no provider is configured (CI, local dev with no keys), falls back
to a deterministic hash-based embedding so the rest of the pipeline
still works. This is INTENTIONAL — callers can test the full retrieval
flow without paying for tokens.

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


def embed(text: str) -> list[float]:
    text = (text or '').strip()
    if not text:
        return [0.0] * EMBEDDING_DIM

    provider = getattr(settings, 'AI_PROVIDER', 'openai')
    model = getattr(settings, 'AI_EMBEDDING_MODEL', 'text-embedding-3-small')

    if provider == 'openai' and getattr(settings, 'OPENAI_API_KEY', ''):
        try:
            from openai import OpenAI

            api_key = settings.OPENAI_API_KEY
            try:
                from plugins.registry import plugin_registry

                ai_plugin = (
                    plugin_registry.get_plugin('ai_assistant')
                    if hasattr(plugin_registry, 'get_plugin')
                    else None
                )
                if ai_plugin is not None:
                    api_key = ai_plugin.get_config_value('openai_api_key') or api_key
            except Exception:  # noqa: BLE001, S110
                pass
            # Bound the request-path cost: this runs inline on chat/RAG/recall
            # turns, and the SDK default (600s timeout + 2 retries) can stall a
            # turn far past the 30s worker budget when the endpoint hangs
            # (audit H3). A missed embedding degrades to the hash fallback below.
            client = OpenAI(api_key=api_key, timeout=10.0, max_retries=0)
            # Pin the output dimension so the OpenAI path honours the module's
            # fixed-dimension contract (text-embedding-3-* default to 1536).
            # Without this, hash-fallback rows (384) and OpenAI rows (1536)
            # coexist and `cosine_similarity` compares mismatched vectors.
            resp = client.embeddings.create(model=model, input=text, dimensions=EMBEDDING_DIM)
            vec = list(resp.data[0].embedding)
            if len(vec) == EMBEDDING_DIM:
                return vec
            logger.warning(
                'OpenAI embed returned %d dims (expected %d); using fallback',
                len(vec),
                EMBEDDING_DIM,
            )
        except Exception as e:  # noqa: BLE001
            logger.warning('OpenAI embed failed (%s); using fallback', e)

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
