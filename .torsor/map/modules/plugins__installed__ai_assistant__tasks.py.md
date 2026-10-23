---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:50'
updated: '2026-10-23T04:51:50'
rules: []
---

# plugins/installed/ai_assistant/tasks.py

Symbols in `plugins/installed/ai_assistant/tasks.py`.

- L14 `refresh_product_embedding(self, product_id)` (function) — Compute and persist the embedding for a product (idempotent on text hash).
- L27 `refresh_product_embeddings_bulk(self, product_ids)` (function) — Compute embeddings for a list of products in a single task.
- L75 `run_completion_task(self, task_id, prompt, system='', max_tokens=1000, temperature=0.6)` (function) — Run an LLM completion off the request thread, write result to cache.
- L114 `reembed_all_products(batch_size: int=50)` (function) — Queue a series of bulk-embed tasks covering every active
- L146 `pulse_daily_refresh()` (function) — Linda's Pulse — refresh proactive insight cards on the dashboard.
- L167 `evaluate_all_product_prices()` (function) — Periodic task (e.g., hourly) to re-evaluate prices for all active products
- L191 `rebuild_knowledge()` (function) — Nightly refresh of Linda's RAG knowledge index.
