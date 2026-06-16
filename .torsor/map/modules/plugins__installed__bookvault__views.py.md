---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:57'
updated: '2026-06-13T00:49:57'
---

# plugins/installed/bookvault/views.py

Symbols in `plugins/installed/bookvault/views.py`.

- L36 `overview(request: HttpRequest)` (function) — Status card + product-link audit + reauth button.
- L81 `disconnect(request: HttpRequest)` (function) — Tell BV to clean up + clear local credentials. Equivalent to
- L101 `connect(request: HttpRequest)` (function) — Mint a fresh BV token. Falls through to the overview page with
- L127 `resend_order(request: HttpRequest, order_id)` (function) — Manual "Resend Order To Bookvault" — mirrors the WP plugin's
- L149 `bulk_link_products(request: HttpRequest)` (function) — 302 to BV's hosted Bulk Products linker with the selected
- L167 `webhook_product_link(request: HttpRequest)` (function) — Inbound BV webhook — sets locations + is_linked on a product/variant.
