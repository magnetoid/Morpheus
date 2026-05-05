"""Product recommendations.

`similar_to(product)` returns products related to the one being viewed.
Uses ProductEmbedding cosine similarity when available; falls back to
"same category" so PDPs always show something useful even before the
embedding refresh task has caught up.
"""
from __future__ import annotations

import logging
from typing import List

from plugins.installed.catalog.models import Product

logger = logging.getLogger('morpheus.ai.recommendations')


def similar_to(product: Product, limit: int = 4) -> List[Product]:
    """Return up to `limit` products related to ``product``.

    Order of preference:
      1. Cosine-similar via ProductEmbedding (best match).
      2. Same category, excluding self (cheap fallback).
      3. Other active products (last-resort filler).
    """
    embed_hits = _by_embedding(product, limit)
    if len(embed_hits) >= limit:
        return embed_hits[:limit]

    seen = {p.id for p in embed_hits} | {product.id}
    if product.category_id:
        fallback_qs = Product.objects.filter(
            status='active', category_id=product.category_id,
        )
    else:
        fallback_qs = Product.objects.filter(status='active')
    fallback = [p for p in fallback_qs[: limit * 3] if p.id not in seen]
    extras = fallback[: limit - len(embed_hits)]
    return embed_hits + extras


def _by_embedding(product: Product, limit: int) -> List[Product]:
    try:
        from plugins.installed.ai_assistant.models import ProductEmbedding
        from plugins.installed.ai_assistant.services.embeddings import cosine_similarity
    except Exception:  # noqa: BLE001
        return []
    try:
        my_emb = ProductEmbedding.objects.filter(product=product).first()
    except Exception:  # noqa: BLE001 — embeddings table not migrated yet
        return []
    if my_emb is None or not my_emb.vector:
        return []
    candidates = (
        ProductEmbedding.objects
        .select_related('product')
        .filter(product__status='active')
        .exclude(product_id=product.id)
    )
    scored: list[tuple[float, Product]] = []
    for emb in candidates.iterator(chunk_size=500):
        if not emb.vector:
            continue
        scored.append((cosine_similarity(my_emb.vector, emb.vector), emb.product))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [p for _, p in scored[:limit]]
