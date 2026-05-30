"""Product recommendations.

`similar_to(product)` returns products related to the one being viewed.
Uses ProductEmbedding cosine similarity when available; falls back to
"same category" so PDPs always show something useful even before the
embedding refresh task has caught up.
"""

from __future__ import annotations

import logging
import random

from django.core.cache import cache
from django.db.models.signals import post_save
from django.dispatch import receiver

from plugins.installed.ai_assistant.models import ProductEmbedding
from plugins.installed.ai_assistant.services.embeddings import cosine_similarity
from plugins.installed.catalog.models import Product

logger = logging.getLogger('morpheus.ai.recommendations')

# 24h — embedding refreshes invalidate the cache via signal below, so a
# day-long TTL is safe and keeps PDPs out of the slow scan path.
_SIMILAR_TTL = 60 * 60 * 24


def _similar_cache_key(product_pk, limit: int) -> str:
    return f'rec:similar:{product_pk}:{limit}'


def invalidate_similar(product_pk) -> None:
    """Drop every cached `similar_to` entry for a product.

    Called from the ProductEmbedding post_save signal so a refreshed
    embedding doesn't keep serving stale neighbours. We don't know
    which `limit` values were cached, so iterate the common small set.
    """
    for limit in (1, 2, 3, 4, 5, 6, 8, 10, 12, 16, 20, 24):
        cache.delete(_similar_cache_key(product_pk, limit))


def similar_to(product: Product, limit: int = 4) -> list[Product]:
    """Return up to `limit` products related to ``product``.

    Order of preference:
      1. Cosine-similar via ProductEmbedding (best match).
      2. Same category, excluding self (cheap fallback).
      3. Other active products (last-resort filler).

    Cached in Redis for 24h keyed on (product.pk, limit). The first
    PDP render is cold (still does the Python cosine scan); every
    subsequent render is a single Redis GET + an IN-query hydrate.
    """
    cache_key = _similar_cache_key(product.pk, limit)
    cached_ids = cache.get(cache_key)
    if cached_ids is not None:
        if not cached_ids:
            return []
        by_id = Product.objects.in_bulk(cached_ids)
        # Preserve cached ordering; drop ids that vanished between writes.
        return [by_id[pid] for pid in cached_ids if pid in by_id]

    results = _compute_similar(product, limit)
    cache.set(cache_key, [p.id for p in results], _SIMILAR_TTL)
    return results


def _compute_similar(product: Product, limit: int) -> list[Product]:
    embed_hits = _by_embedding(product, limit)
    if len(embed_hits) >= limit:
        return embed_hits[:limit]

    seen = {p.id for p in embed_hits} | {product.id}
    if product.category_id:
        fallback_qs = Product.objects.filter(
            status='active',
            category_id=product.category_id,
        )
    else:
        fallback_qs = Product.objects.filter(status='active')
    candidates = [p for p in fallback_qs if p.id not in seen]
    # Without a seed, the default Meta.ordering = ['-created_at']
    # returns the same N most-recently-created siblings for every
    # product in the category — leading to "Shakespeare trio for every
    # fiction PDP". Seed on product.id so each product gets a varied
    # but reproducible sibling set; re-running apply_internal_links
    # yields the same answer for the same product.
    random.Random(str(product.id)).shuffle(candidates)  # noqa: S311 — deterministic sibling shuffle, not security-sensitive
    extras = candidates[: limit - len(embed_hits)]
    return embed_hits + extras


def _by_embedding(product: Product, limit: int) -> list[Product]:
    try:
        my_emb = ProductEmbedding.objects.filter(product=product).first()
    except Exception:  # noqa: BLE001 — embeddings table not migrated yet
        return []
    if my_emb is None or not my_emb.vector:
        return []
    candidates = (
        ProductEmbedding.objects.select_related('product')
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


# ── Signal wiring ─────────────────────────────────────────────────────
# When an embedding row is (re)written, flush the cached neighbour list
# for that product so the next PDP render recomputes against the fresh
# vector.


@receiver(
    post_save,
    sender=ProductEmbedding,
    dispatch_uid='ai_assistant.rec.invalidate_similar',
)
def _on_embedding_saved(sender, instance, **kwargs):  # noqa: ARG001
    try:
        invalidate_similar(instance.product_id)
    except Exception:  # noqa: BLE001 — never let cache plumbing break a save
        logger.warning(
            'invalidate_similar failed for %s',
            instance.product_id,
            exc_info=True,
        )
