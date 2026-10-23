---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:52'
updated: '2026-10-23T04:51:52'
rules: []
---

# plugins/installed/tracking/templatetags/tracking.py

Symbols in `plugins/installed/tracking/templatetags/tracking.py`.

- L43 `_settings()` (function)
- L50 `_has_consent(request, category: str)` (function) — True if the visitor has opted in to ``category`` (analytics /
- L74 `gtm_consent_default()` (function) — Emit Consent Mode v2 defaults **before** any GTM/gtag boot.
- L96 `gtm_head(context)` (function) — Emit the GTM head snippet. No-op when GTM container is not
- L119 `gtm_noscript_body(context)` (function) — Emit the immediate-after-`<body>` noscript fallback iframe.
- L134 `_datalayer_push(event_name: str, ecommerce: dict[str, Any])` (function) — Render a dataLayer.push() pair with the mandatory ecommerce-null reset.
- L152 `dl_view_item(product)` (function) — `view_item` dataLayer push for the PDP.
- L171 `dl_view_item_list(items, list_id: str='', list_name: str='')` (function) — `view_item_list` push for the PLP / category page.
- L190 `dl_purchase(order)` (function) — `purchase` push for the order confirmation page. The
- L213 `_ads_config()` (function) — Read Google Ads conversion knobs from the tracking plugin's
- L233 `gads_purchase_conversion(context, order)` (function) — Emit a Google Ads `conversion` event for the order. Only fires
- L294 `tracking_consent_banner()` (function) — Retired in v0.113.0 (the consent app is the one cookie banner); renders
