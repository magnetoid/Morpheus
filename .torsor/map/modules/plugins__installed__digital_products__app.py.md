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

# plugins/installed/digital_products/app.py

Symbols in `plugins/installed/digital_products/app.py`.

- L26 `DigitalProductsPlugin` (class)
- L37 `ready(self)` (method)
- L57 `contribute_storefront_blocks(self)` (method)
- L68 `on_account_summary(self, value, user=None, **kwargs)` (method) — Fold this customer's active download count into the account summary.
- L91 `_register_beat_schedule(self)` (method)
- L107 `get_config_schema(self)` (method)
- L128 `contribute_settings_panel(self)` (method)
- L136 `on_order_paid(self, order, **kwargs)` (method) — Mint DownloadTokens for each digital line on a paid order, fire
