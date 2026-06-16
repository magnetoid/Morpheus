---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:57'
updated: '2026-06-13T00:49:57'
---

# plugins/installed/ai_assistant/services/search.py

Symbols in `plugins/installed/ai_assistant/services/search.py`.

- L35 `_normalize_query(q: str)` (function)
- L39 `_query_embed_cache_key(q_norm: str)` (function)
- L44 `_cached_query_embedding(query: str)` (function) — Return cached query embedding or None on miss.
- L66 `_keyword_fallback(query: str, limit: int)` (function)
- L88 `semantic_search(query: str, limit: int=8)` (function) — Returns `(products, used_embedding)`.
- L131 `hybrid_search(query: str, *, top_k: int=20)` (function) — BM25 + dense ranking fused via Reciprocal Rank Fusion.
- L174 `_bm25_rank(query: str, *, limit: int)` (function) — Postgres FTS pass. Empty list on non-Postgres backends.
- L199 `_dense_rank(query: str, *, limit: int)` (function) — Cosine similarity over ProductEmbedding.
- L234 `upsert_product_embedding(product: Product)` (function) — Compute and persist the embedding for a single product (idempotent).
- L273 `warm_query_embedding(self, q_norm: str)` (function) — Pre-compute and cache an embedding for a normalized search query.
