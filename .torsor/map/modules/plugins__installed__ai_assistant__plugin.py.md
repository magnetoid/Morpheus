---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-02T18:07:52'
updated: '2026-06-02T18:07:52'
---

# plugins/installed/ai_assistant/plugin.py

Symbols in `plugins/installed/ai_assistant/plugin.py`.

- L16 `AIAssistantPlugin` (class)
- L33 `ready(self)` (method)
- L60 `_register_pulse_schedule(self)` (method)
- L84 `_pulse_event_nudge(self, **_kwargs)` (method) — Trigger a Pulse refresh on key events so the dashboard panel
- L94 `on_order_placed(self, order, **kwargs)` (method) — Update recommendation model after purchase.
- L99 `on_customer_registered(self, customer, **kwargs)` (method) — Initialize memory store for new customer.
- L104 `on_cart_abandoned(self, cart, **kwargs)` (method) — Generate AI-personalized cart recovery message.
- L109 `on_product_created(self, product, **kwargs)` (method) — If product has no description, auto-generate one. Always (re)embed.
- L116 `on_product_updated(self, product, **kwargs)` (method)
- L119 `_enqueue_embedding(self, product)` (method) — Best-effort: schedule an embedding refresh; never raise from a hook.
- L131 `on_calculate_price(self, value, product=None, customer=None, **kwargs)` (method) — AI dynamic pricing hook — returns adjusted price if strategy active.
- L138 `get_config_schema(self)` (method)
- L270 `contribute_settings_panel(self)` (method)
