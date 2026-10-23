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

# plugins/installed/ai_assistant/app.py

Symbols in `plugins/installed/ai_assistant/app.py`.

- L22 `AIAssistantPlugin` (class)
- L39 `ready(self)` (method)
- L128 `_autonomy_gate(self, value, **_)` (method)
- L131 `_register_pulse_schedule(self)` (method)
- L156 `on_dashboard_panels(self, value, date_range=None, **kwargs)` (method) — Fold unread insights, the Pulse top-5, and the provider half of
- L200 `on_setup_steps(self, value, **kwargs)` (method) — Append the connect-an-AI-provider first-run step.
- L221 `_pulse_event_nudge(self, **_kwargs)` (method) — Trigger a Pulse refresh on key events so the dashboard panel
- L232 `on_ai_usage_today(self, value, since=None, **_)` (method) — Today's provider-gateway calls (AIInteraction rows), for the spend cap.
- L246 `on_brain_signals(self, value, **kwargs)` (method) — Merge unread merchant insights into the Brain's Improvements panel
- L265 `on_search_ranked_ids(self, value, query='', limit=80, **kwargs)` (method) — SEARCH_RANKED_IDS: hybrid (BM25 + embeddings) ranking for search.
- L271 `on_similar_products(self, value, product=None, limit=4, **kwargs)` (method) — SIMILAR_PRODUCTS: content-similar products for the PDP.
- L279 `on_product_created(self, product, **kwargs)` (method) — (Re)embed for search. Descriptions are written on request from the
- L285 `on_product_updated(self, product, **kwargs)` (method)
- L288 `_enqueue_embedding(self, product)` (method) — Best-effort: schedule an embedding refresh; never raise from a hook.
- L303 `on_calculate_price(self, value, product=None, customer=None, **kwargs)` (method) — AI dynamic pricing hook — returns adjusted price if strategy active.
- L311 `get_config_schema(self)` (method)
- L611 `contribute_settings_panel(self)` (method)
- L619 `contribute_agent_tools(self)` (method) — Expose AI-signal services to Linda + the agent layer, each behind its
