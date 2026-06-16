---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:57'
updated: '2026-06-13T00:49:57'
---

# plugins/installed/ai_assistant/tasks.py

Symbols in `plugins/installed/ai_assistant/tasks.py`.

- L11 `update_recommendations_after_order(order_id)` (function)
- L20 `initialize_customer_memory(customer_id)` (function)
- L29 `generate_cart_recovery(cart_id)` (function)
- L39 `generate_product_description(product_id)` (function)
- L48 `refresh_product_embedding(self, product_id)` (function) — Compute and persist the embedding for a product (idempotent on text hash).
- L61 `refresh_product_embeddings_bulk(self, product_ids)` (function) — Compute embeddings for a list of products in a single task.
- L109 `run_completion_task(self, task_id, prompt, system='', max_tokens=1000, temperature=0.6)` (function) — Run an LLM completion off the request thread, write result to cache.
- L148 `reembed_all_products(batch_size: int=50)` (function) — Queue a series of bulk-embed tasks covering every active
- L175 `pulse_daily_refresh()` (function) — Linda's Pulse — refresh proactive insight cards on the dashboard.
- L194 `evaluate_all_product_prices()` (function) — Periodic task (e.g., hourly) to re-evaluate prices for all active products
