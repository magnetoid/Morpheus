---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:57'
updated: '2026-06-13T00:49:57'
---

# plugins/installed/ai_assistant/plugin.py

Symbols in `plugins/installed/ai_assistant/plugin.py`.

- L21 `AIAssistantPlugin` (class)
- L38 `ready(self)` (method)
- L76 `_register_pulse_schedule(self)` (method)
- L101 `on_dashboard_panels(self, value, date_range=None, **kwargs)` (method) — Fold unread insights, the Pulse top-5, and the provider half of
- L140 `on_setup_steps(self, value, **kwargs)` (method) — Append the connect-an-AI-provider first-run step.
- L161 `_pulse_event_nudge(self, **_kwargs)` (method) — Trigger a Pulse refresh on key events so the dashboard panel
- L172 `on_order_placed(self, order, **kwargs)` (method) — Update recommendation model after purchase.
- L178 `on_customer_registered(self, customer, **kwargs)` (method) — Initialize memory store for new customer.
- L184 `on_cart_abandoned(self, cart, **kwargs)` (method) — Generate AI-personalized cart recovery message.
- L190 `on_product_created(self, product, **kwargs)` (method) — If product has no description, auto-generate one. Always (re)embed.
- L198 `on_product_updated(self, product, **kwargs)` (method)
- L201 `_enqueue_embedding(self, product)` (method) — Best-effort: schedule an embedding refresh; never raise from a hook.
- L216 `on_calculate_price(self, value, product=None, customer=None, **kwargs)` (method) — AI dynamic pricing hook — returns adjusted price if strategy active.
- L224 `get_config_schema(self)` (method)
- L414 `contribute_settings_panel(self)` (method)
