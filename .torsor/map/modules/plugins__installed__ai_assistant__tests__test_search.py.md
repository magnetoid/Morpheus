---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-09T21:57:01'
updated: '2026-06-09T21:57:01'
---

# plugins/installed/ai_assistant/tests/test_search.py

Symbols in `plugins/installed/ai_assistant/tests/test_search.py`.

- L21 `EmbeddingTests` (class)
- L23 `test_embed_returns_fixed_dim_floats(self)` (method)
- L28 `test_embed_is_deterministic(self)` (method)
- L31 `test_cosine_self_similarity_is_one(self)` (method)
- L36 `SemanticSearchTests` (class)
- L38 `setUp(self)` (method)
- L52 `test_keyword_fallback_when_no_embeddings(self)` (method)
- L58 `test_used_embedding_when_embeddings_present(self)` (method)
- L67 `test_upsert_is_idempotent_on_unchanged_text(self)` (method)
- L75 `HybridSearchTests` (class) — Golden queries for BM25 + dense + RRF fusion.
- L78 `setUp(self)` (method)
- L98 `test_hybrid_falls_back_when_query_empty(self)` (method)
- L103 `test_hybrid_keyword_match_without_embeddings(self)` (method)
- L110 `test_hybrid_dense_pass_surfaces_semantic_match(self)` (method)
