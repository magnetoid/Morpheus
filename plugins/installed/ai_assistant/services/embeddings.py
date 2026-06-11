"""Compat shim — embeddings now live in `core.embeddings`.

Existing imports (`from plugins.installed.ai_assistant.services.embeddings
import embed`) continue to work; new code should import from
`core.embeddings` directly.
"""

from __future__ import annotations

from core.embeddings import EMBEDDING_DIM, _hash_embedding, cosine_similarity, embed

__all__ = ['EMBEDDING_DIM', '_hash_embedding', 'cosine_similarity', 'embed']
