---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:49'
updated: '2026-10-23T04:51:49'
rules: []
---

# core/context_processors.py

Symbols in `core/context_processors.py`.

- L6 `_store_identity()` (function) — Merchant-editable store identity, from the DB row they actually edit.
- L43 `store_settings(request)` (function)
- L64 `_gdpr_enabled()` (function) — Cached read of the GDPR master switch (runs on every storefront page).
- L80 `_product_placeholder_url()` (function) — URL of the configured product placeholder image, or '' if unset/unavailable.
- L91 `display_currency(request)` (function) — Resolve the visitor's preferred display currency.
- L115 `channel_context(request)` (function) — Expose the resolved StoreChannel + its currency/country to every template.
