---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-02T18:07:52'
updated: '2026-06-02T18:07:52'
---

# plugins/installed/bookvault/views.py

Symbols in `plugins/installed/bookvault/views.py`.

- L36 `overview(request: HttpRequest)` (function) — Status card + product-link audit + reauth button.
- L74 `disconnect(request: HttpRequest)` (function) — Tell BV to clean up + clear local credentials. Equivalent to
- L95 `connect(request: HttpRequest)` (function) — Mint a fresh BV token. Falls through to the overview page with
- L121 `resend_order(request: HttpRequest, order_id)` (function) — Manual "Resend Order To Bookvault" — mirrors the WP plugin's
- L143 `bulk_link_products(request: HttpRequest)` (function) — 302 to BV's hosted Bulk Products linker with the selected
- L161 `webhook_product_link(request: HttpRequest)` (function) — Inbound BV webhook — sets locations + is_linked on a product/variant.
