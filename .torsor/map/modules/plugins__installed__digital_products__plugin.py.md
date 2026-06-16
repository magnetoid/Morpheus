---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:58'
updated: '2026-06-13T00:49:58'
---

# plugins/installed/digital_products/plugin.py

Symbols in `plugins/installed/digital_products/plugin.py`.

- L25 `DigitalProductsPlugin` (class)
- L36 `ready(self)` (method)
- L56 `contribute_storefront_blocks(self)` (method)
- L67 `on_account_summary(self, value, user=None, **kwargs)` (method) — Fold this customer's active download count into the account summary.
- L90 `_register_beat_schedule(self)` (method)
- L106 `get_config_schema(self)` (method)
- L127 `contribute_settings_panel(self)` (method)
- L135 `on_order_paid(self, order, **kwargs)` (method) — Mint DownloadTokens for each digital line on a paid order, fire
