---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-02T18:07:52'
updated: '2026-06-02T18:07:52'
---

# plugins/installed/post_purchase/handlers.py

Symbols in `plugins/installed/post_purchase/handlers.py`.

- L27 `on_order_placed(*, order=None, **_)` (function) — Schedule the tracking_sent step when shipment is created.
- L53 `on_order_fulfilled(*, order=None, **_)` (function) — Schedule the three follow-up steps at their configured delays.
- L92 `_config()` (function) — Resolve PluginConfig['post_purchase']['config'] with sane defaults.
