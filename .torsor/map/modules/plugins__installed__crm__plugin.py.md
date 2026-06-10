---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-10T20:08:49'
updated: '2026-06-10T20:08:49'
---

# plugins/installed/crm/plugin.py

Symbols in `plugins/installed/crm/plugin.py`.

- L13 `CrmPlugin` (class)
- L25 `ready(self)` (method)
- L39 `_register_beat_schedule(self)` (method)
- L55 `on_customer_registered(self, customer, **kwargs)` (method) — If a lead exists for this email, mark it converted; otherwise create one.
- L82 `on_order_placed(self, order, **kwargs)` (method) — Append an order activity row to the customer's timeline.
- L103 `on_cart_abandoned(self, cart, **kwargs)` (method) — Create a 24-hour follow-up task on the customer (if there is one).
- L125 `contribute_agent_tools(self)` (method)
- L135 `contribute_skills(self)` (method) — The CRM skill — opt in via skills=['crm'] for sales-pipeline work.
- L165 `contribute_agents(self)` (method)
- L169 `contribute_dashboard_pages(self)` (method)
- L211 `contribute_settings_panel(self)` (method)
- L219 `get_config_schema(self)` (method)
