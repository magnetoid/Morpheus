---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:57'
updated: '2026-06-13T00:49:57'
---

# plugins/installed/crm/plugin.py

Symbols in `plugins/installed/crm/plugin.py`.

- L12 `CrmPlugin` (class)
- L24 `ready(self)` (method)
- L40 `_register_beat_schedule(self)` (method)
- L57 `on_activity_feed(self, value, limit=20, **kwargs)` (method) — Fold recent newsletter signups into the dashboard home feed
- L76 `on_customer_registered(self, customer, **kwargs)` (method) — If a lead exists for this email, mark it converted; otherwise create one.
- L110 `on_order_placed(self, order, **kwargs)` (method) — Append an order activity row to the customer's timeline.
- L134 `on_cart_abandoned(self, cart, **kwargs)` (method) — Create a 24-hour follow-up task on the customer (if there is one).
- L156 `contribute_agent_tools(self)` (method)
- L175 `contribute_skills(self)` (method) — The CRM skill — opt in via skills=['crm'] for sales-pipeline work.
- L216 `contribute_agents(self)` (method)
- L221 `contribute_dashboard_pages(self)` (method)
- L263 `contribute_settings_panel(self)` (method)
- L271 `get_config_schema(self)` (method)
