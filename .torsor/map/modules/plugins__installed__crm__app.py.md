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

# plugins/installed/crm/app.py

Symbols in `plugins/installed/crm/app.py`.

- L13 `CrmPlugin` (class)
- L25 `ready(self)` (method)
- L50 `_register_beat_schedule(self)` (method)
- L67 `on_newsletter_subscribed(self, email=None, source='newsletter', **kwargs)` (method) — NEWSLETTER_SUBSCRIBED → CRM Lead (idempotent, fail-soft).
- L82 `on_activity_feed(self, value, limit=20, **kwargs)` (method) — Fold recent newsletter signups into the dashboard home feed
- L101 `on_customer_registered(self, customer, **kwargs)` (method) — If a lead exists for this email, mark it converted; otherwise create one.
- L135 `on_order_placed(self, order, **kwargs)` (method) — Append an order activity row to the customer's timeline.
- L159 `on_cart_abandoned(self, cart, **kwargs)` (method) — Create a 24-hour follow-up task on the customer (if there is one).
- L181 `contribute_agent_tools(self)` (method)
- L204 `contribute_skills(self)` (method) — The CRM skill — opt in via skills=['crm'] for sales-pipeline work.
- L245 `contribute_agents(self)` (method)
- L250 `contribute_dashboard_pages(self)` (method)
- L301 `contribute_storefront_blocks(self)` (method)
- L312 `contribute_email_templates(self)` (method)
- L325 `contribute_settings_panel(self)` (method)
- L333 `get_config_schema(self)` (method)
