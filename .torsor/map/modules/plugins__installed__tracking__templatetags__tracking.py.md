---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:58'
updated: '2026-06-13T00:49:58'
---

# plugins/installed/tracking/templatetags/tracking.py

Symbols in `plugins/installed/tracking/templatetags/tracking.py`.

- L44 `_settings()` (function)
- L51 `_has_consent(request, category: str)` (function) — True if the visitor has opted in to ``category`` (analytics /
- L75 `gtm_consent_default()` (function) — Emit Consent Mode v2 defaults **before** any GTM/gtag boot.
- L97 `gtm_head(context)` (function) — Emit the GTM head snippet. No-op when GTM container is not
- L120 `gtm_noscript_body(context)` (function) — Emit the immediate-after-`<body>` noscript fallback iframe.
- L135 `_datalayer_push(event_name: str, ecommerce: dict[str, Any])` (function) — Render a dataLayer.push() pair with the mandatory ecommerce-null reset.
- L153 `dl_view_item(product)` (function) — `view_item` dataLayer push for the PDP.
- L172 `dl_view_item_list(items, list_id: str='', list_name: str='')` (function) — `view_item_list` push for the PLP / category page.
- L191 `dl_purchase(order)` (function) — `purchase` push for the order confirmation page. The
- L214 `_ads_config()` (function) — Read Google Ads conversion knobs from the tracking plugin's
- L234 `gads_purchase_conversion(order)` (function) — Emit a Google Ads `conversion` event for the order. Only fires
- L291 `tracking_consent_banner()` (function) — Tiny consent banner (off by default). When enabled the
