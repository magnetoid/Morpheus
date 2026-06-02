---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-02T18:07:52'
updated: '2026-06-02T18:07:52'
---

# plugins/installed/ai_assistant/services/recommendations.py

Symbols in `plugins/installed/ai_assistant/services/recommendations.py`.

- L29 `_similar_cache_key(product_pk, limit: int)` (function)
- L33 `invalidate_similar(product_pk)` (function) — Drop every cached `similar_to` entry for a product.
- L44 `similar_to(product: Product, limit: int=4)` (function) — Return up to `limit` products related to ``product``.
- L70 `_compute_similar(product: Product, limit: int)` (function)
- L95 `_by_embedding(product: Product, limit: int)` (function)
- L127 `_on_embedding_saved(sender, instance, **kwargs)` (function)
