---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-02T18:07:52'
updated: '2026-06-02T18:07:52'
---

# plugins/installed/ai_assistant/tasks.py

Symbols in `plugins/installed/ai_assistant/tasks.py`.

- L9 `update_recommendations_after_order(order_id)` (function)
- L18 `initialize_customer_memory(customer_id)` (function)
- L27 `generate_cart_recovery(cart_id)` (function)
- L37 `generate_product_description(product_id)` (function)
- L46 `refresh_product_embedding(self, product_id)` (function) — Compute and persist the embedding for a product (idempotent on text hash).
- L59 `refresh_product_embeddings_bulk(self, product_ids)` (function) — Compute embeddings for a list of products in a single task.
- L107 `run_completion_task(self, task_id, prompt, system='', max_tokens=1000, temperature=0.6)` (function) — Run an LLM completion off the request thread, write result to cache.
- L146 `reembed_all_products(batch_size: int=50)` (function) — Queue a series of bulk-embed tasks covering every active
- L173 `pulse_daily_refresh()` (function) — Linda's Pulse — refresh proactive insight cards on the dashboard.
- L192 `evaluate_all_product_prices()` (function) — Periodic task (e.g., hourly) to re-evaluate prices for all active products
