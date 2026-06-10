---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-10T20:08:49'
updated: '2026-06-10T20:08:49'
---

# plugins/installed/advanced_payments/sync.py

Symbols in `plugins/installed/advanced_payments/sync.py`.

- L34 `sync_gateway_config(*args, **kwargs)` (function) — Upsert the ``cod``/``test`` PaymentGatewayConfig rows from the panel.
- L61 `_on_plugin_config_saved(sender, instance, **kwargs)` (function) — post_save(PluginConfig) receiver — resync only on our own row.
