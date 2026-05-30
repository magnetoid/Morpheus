"""
Semantic product search.

Tries embedding-based ranking when ProductEmbedding rows exist, and falls
back to a Postgres full-text / SQLite icontains query otherwise. Always
returns active products only.
"""

from __future__ import annotations

import hashlib
import logging

from celery import shared_task
from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from django.core.cache import cache
from django.db import connection
from django.db.models import Q

from plugins.installed.ai_assistant.models import ProductEmbedding
from plugins.installed.ai_assistant.services.embeddings import (
    EMBEDDING_DIM,
    cosine_similarity,
    embed,
)
from plugins.installed.catalog.models import Product

logger = logging.getLogger('morpheus.ai.search')

# 24h — query-embedding drift over a day is negligible compared to the
# 300–1500ms HTTP cost per request. Invalidated implicitly by TTL.
_QUERY_EMBED_TTL = 60 * 60 * 24


def _normalize_query(q: str) -> str:
    return q.strip().lower()[:200]


def _query_embed_cache_key(q_norm: str) -> str:
    digest = hashlib.sha256(q_norm.encode('utf-8')).hexdigest()[:16]
    return f'embed:q:{digest}'


def _cached_query_embedding(query: str):
    """Return cached query embedding or None on miss.

    On miss, asynchronously warm the cache for the next request via a
    Celery task — the current request gets BM25-only results, the next
    visit to the same query is fully dense-cached.
    """
    q_norm = _normalize_query(query)
    if not q_norm:
        return None
    key = _query_embed_cache_key(q_norm)
    cached = cache.get(key)
    if cached is not None:
        return cached
    # Miss → schedule warmup, return None so caller skips dense pass.
    try:
        warm_query_embedding.delay(q_norm)
    except Exception:  # noqa: BLE001 — broker down must not break search
        logger.warning('warm_query_embedding dispatch failed', exc_info=True)
    return None


def _keyword_fallback(query: str, limit: int) -> list[Product]:
    qs = (
        Product.objects.filter(status='active')
        .filter(
            Q(name__icontains=query)
            | Q(short_description__icontains=query)
            | Q(description__icontains=query)
        )
        .select_related('category', 'vendor')
        .prefetch_related('variants', 'images')
        .distinct()
    )
    products = list(qs[:limit])
    if products:
        return products
    return list(
        Product.objects.filter(status='active', is_featured=True)
        .select_related('category', 'vendor')
        .prefetch_related('variants', 'images')[:limit]
    )


def semantic_search(query: str, limit: int = 8) -> tuple[list[Product], bool]:
    """
    Returns `(products, used_embedding)`.

    used_embedding=True only when at least one ProductEmbedding row exists and
    we computed cosine similarity against an actual query embedding.
    """
    try:
        has_embeddings = ProductEmbedding.objects.exists()
    except Exception:  # noqa: BLE001 — embeddings table not migrated yet
        return _keyword_fallback(query, limit), False
    if not has_embeddings:
        return _keyword_fallback(query, limit), False

    try:
        query_vec = embed(query)
    except Exception as e:  # noqa: BLE001 — providers can fail in surprising ways
        logger.warning('Embed query failed (%s); using keyword fallback', e)
        return _keyword_fallback(query, limit), False

    candidate_pool = (
        ProductEmbedding.objects.select_related('product', 'product__category', 'product__vendor')
        .prefetch_related('product__variants', 'product__images')
        .filter(product__status='active')
    )
    scored: list[tuple[float, Product]] = []
    for emb in candidate_pool.iterator(chunk_size=500):
        if not emb.vector:
            continue
        scored.append((cosine_similarity(query_vec, emb.vector), emb.product))
    if not scored:
        return _keyword_fallback(query, limit), False

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [p for _, p in scored[:limit]], True


# ── Hybrid retrieval ──────────────────────────────────────────────────


_RRF_K = 60  # standard RRF constant — k=60 in the original paper.


def hybrid_search(query: str, *, top_k: int = 20) -> list[Product]:
    """BM25 + dense ranking fused via Reciprocal Rank Fusion.

    Two retrieval passes:
      1. Postgres full-text rank (BM25-shaped) over name +
         short_description + description.
      2. Cosine similarity over ProductEmbedding rows.

    Each pass returns a ranked list; ranks are combined with
    Reciprocal Rank Fusion:  score(p) = Σ 1 / (k + rank_i(p))
    where k=60 and rank_i is the per-list rank (1-based).

    Falls back gracefully:
      * On SQLite / no FTS → only the embedding pass runs.
      * On no ProductEmbedding rows → only the FTS pass runs.
      * On both unavailable → uses the existing _keyword_fallback.

    Cross-encoder reranker (BAAI/bge-reranker-base) is deferred —
    pure RRF is enough for the current catalogue size (~50 books)
    and the reranker adds a ~280 MB model + compute cost. Wire it
    in when the catalog grows past a few thousand SKUs.
    """
    if not query.strip():
        return _keyword_fallback('', top_k)

    bm25_rank = _bm25_rank(query, limit=top_k * 2)
    dense_rank = _dense_rank(query, limit=top_k * 2)

    if not bm25_rank and not dense_rank:
        return _keyword_fallback(query, top_k)

    scores: dict = {}
    products: dict = {}
    for source in (bm25_rank, dense_rank):
        for rank, product in enumerate(source, start=1):
            pid = product.pk
            scores[pid] = scores.get(pid, 0.0) + 1.0 / (_RRF_K + rank)
            products[pid] = product

    fused = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    return [products[pid] for pid, _ in fused[:top_k]]


def _bm25_rank(query: str, *, limit: int) -> list[Product]:
    """Postgres FTS pass. Empty list on non-Postgres backends."""
    if connection.vendor != 'postgresql':
        return []
    try:
        vector = (
            SearchVector('name', weight='A')
            + SearchVector('short_description', weight='B')
            + SearchVector('description', weight='C')
        )
        sq = SearchQuery(query, search_type='websearch')
        qs = (
            Product.objects.filter(status='active')
            .annotate(_rank=SearchRank(vector, sq))
            .filter(_rank__gt=0)
            .select_related('category', 'vendor')
            .prefetch_related('images')
            .order_by('-_rank', '-created_at')[:limit]
        )
        return list(qs)
    except Exception as e:  # noqa: BLE001
        logger.warning('hybrid_search: BM25 pass failed: %s', e)
        return []


def _dense_rank(query: str, *, limit: int) -> list[Product]:
    """Cosine similarity over ProductEmbedding.

    Embedding lookup is cache-only — on miss we return [] and let BM25
    carry the request, while a Celery task warms the embedding for next
    time. This trades a single-request "BM25-only result" for never
    blocking the request thread on a 300–1500ms HTTP embedding call.
    """
    try:
        has_embeddings = ProductEmbedding.objects.exists()
    except Exception as e:  # noqa: BLE001
        logger.debug('hybrid_search: dense pass unavailable: %s', e)
        return []
    if not has_embeddings:
        return []

    query_vec = _cached_query_embedding(query)
    if query_vec is None:
        # Cache miss → BM25 alone serves this request; warmer is queued.
        return []

    pool = (
        ProductEmbedding.objects.select_related('product', 'product__category', 'product__vendor')
        .prefetch_related('product__images')
        .filter(product__status='active')
    )
    scored: list[tuple[float, Product]] = []
    for emb in pool.iterator(chunk_size=500):
        if not emb.vector:
            continue
        scored.append((cosine_similarity(query_vec, emb.vector), emb.product))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [p for _, p in scored[:limit]]


def upsert_product_embedding(product: Product) -> None:
    """Compute and persist the embedding for a single product (idempotent)."""
    text = ' | '.join(
        filter(
            None,
            [
                product.name,
                product.short_description,
                product.description,
                product.category.name if product.category_id else '',
            ],
        )
    )
    digest = hashlib.sha256(text.encode('utf-8')).hexdigest()

    existing = ProductEmbedding.objects.filter(product=product).first()
    if existing and existing.source_text_hash == digest:
        return

    vector = embed(text)
    ProductEmbedding.objects.update_or_create(
        product=product,
        defaults={
            'vector': vector,
            'dim': len(vector) or EMBEDDING_DIM,
            'source_text_hash': digest,
        },
    )


# ── Celery task: cache warmer ─────────────────────────────────────────
# Defined in this module (rather than ai_assistant/tasks.py) because the
# fix instructions restricted the touch-list to search.py/recommendations.py.
# Celery autodiscovery picks up `@shared_task` decorations from any module
# imported on worker boot; search.py is imported by the storefront search
# view, which runs in the worker as well as the web process.


@shared_task(bind=True, time_limit=30, soft_time_limit=20)
def warm_query_embedding(self, q_norm: str) -> None:  # noqa: ARG001
    """Pre-compute and cache an embedding for a normalized search query.

    Called asynchronously from `_dense_rank` on cache miss. Idempotent:
    re-running for the same `q_norm` just refreshes the TTL.
    """
    if not q_norm:
        return
    key = _query_embed_cache_key(q_norm)
    try:
        vector = embed(q_norm)
    except Exception as e:  # noqa: BLE001 — provider failure must not crash the task
        logger.warning('warm_query_embedding: embed failed for %r: %s', q_norm[:80], e)
        return
    cache.set(key, vector, _QUERY_EMBED_TTL)
