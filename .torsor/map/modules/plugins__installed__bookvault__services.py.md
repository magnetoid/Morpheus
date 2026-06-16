---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:57'
updated: '2026-06-13T00:49:57'
---

# plugins/installed/bookvault/services.py

Symbols in `plugins/installed/bookvault/services.py`.

- L56 `_config()` (function) — Pull the bookvault plugin's PluginConfig.config dict.
- L71 `_save_config(updates: dict[str, Any])` (function)
- L84 `is_authenticated()` (function)
- L89 `store_url()` (function) — Best-effort canonical site URL for the BV auth handshake.
- L97 `currency()` (function)
- L104 `authenticate(*, store_url_override: str='')` (function) — Mint a fresh BV token by GETting auth.bookvault.app/api/WooAuth.
- L141 `_isbn_lines(cart_or_order)` (function) — Extract ``[{ISBN, Quantity}]`` from a Cart or Order's items.
- L167 `get_shipping_rates(*, cart=None, order_lines: list[dict] | None=None, country_code: str='', postcode: str='', service_level: str='NotSpecified')` (function) — POST to /woocommerce/shipping and return the list of services.
- L231 `_order_payload(order)` (function) — Serialise an Order into the shape BV's /orders/create expects.
- L278 `send_order(*, order)` (function) — POST a paid order to BV's /woocommerce/orders/create.
- L330 `portal_order_url(bv_ref: str)` (function) — Build the deep link the admin clicks to view the order in BV's portal.
- L337 `portal_apps_url()` (function) — The 'Add Products' CTA on the dashboard once the store is authed.
- L342 `portal_orders_url()` (function) — The 'View Orders' CTA on the dashboard once the store is authed.
- L347 `authorize_url(*, action: str='')` (function) — Build the OAuth-style register / login URL the unauthed empty
- L370 `send_uninstall_notification()` (function) — POST to /woocommerce/Uninstall so BV's backend can clean up.
- L395 `disconnect()` (function) — Hard-disconnect: tell BV to clean up + drop local credentials.
- L407 `bulk_products_link(product_ids: list[str])` (function) — Build the URL that hands product IDs off to BV's hosted Bulk
- L423 `product_link_status(product)` (function) — Aggregate status across a product's variants for the admin
- L429 `bulk_link_status_for(product_ids)` (function) — One-query batched version of ``product_link_status`` for the
