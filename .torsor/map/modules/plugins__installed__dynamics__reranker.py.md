---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:51'
updated: '2026-10-23T04:51:51'
rules: []
---

# plugins/installed/dynamics/reranker.py

Symbols in `plugins/installed/dynamics/reranker.py`.

- L29 `thompson_rerank(product_ids: list, segment: str, propensity: dict, *, category_of: dict | None=None, exploration_rate: float=_EXPLORATION_RATE, per_category_cap: int=_PER_CATEGORY_CAP)` (function) — Rerank ``product_ids`` by a Thompson draw blended with propensity, then
- L63 `_arms_for(product_ids: list, segment: str)` (function) — product_id -> (alpha, beta) for this segment. Missing rows are cold-start.
- L76 `_inject_exploration(ordered: list, rate: float)` (function) — Light, order-preserving exploration: each non-head position has a small
- L89 `_cap_by_category(ordered: list, category_of: dict, cap: int)` (function) — Keep at most ``cap`` items per category in the head; overflow slides to the
