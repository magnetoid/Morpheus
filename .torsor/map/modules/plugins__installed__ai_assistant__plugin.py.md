---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-10T20:08:49'
updated: '2026-06-10T20:08:49'
---

# plugins/installed/ai_assistant/plugin.py

Symbols in `plugins/installed/ai_assistant/plugin.py`.

- L21 `AIAssistantPlugin` (class)
- L38 `ready(self)` (method)
- L65 `_register_pulse_schedule(self)` (method)
- L90 `_pulse_event_nudge(self, **_kwargs)` (method) — Trigger a Pulse refresh on key events so the dashboard panel
- L101 `on_order_placed(self, order, **kwargs)` (method) — Update recommendation model after purchase.
- L107 `on_customer_registered(self, customer, **kwargs)` (method) — Initialize memory store for new customer.
- L113 `on_cart_abandoned(self, cart, **kwargs)` (method) — Generate AI-personalized cart recovery message.
- L119 `on_product_created(self, product, **kwargs)` (method) — If product has no description, auto-generate one. Always (re)embed.
- L127 `on_product_updated(self, product, **kwargs)` (method)
- L130 `_enqueue_embedding(self, product)` (method) — Best-effort: schedule an embedding refresh; never raise from a hook.
- L145 `on_calculate_price(self, value, product=None, customer=None, **kwargs)` (method) — AI dynamic pricing hook — returns adjusted price if strategy active.
- L153 `get_config_schema(self)` (method)
- L343 `contribute_settings_panel(self)` (method)
