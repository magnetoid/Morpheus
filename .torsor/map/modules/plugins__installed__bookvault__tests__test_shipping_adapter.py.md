---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:57'
updated: '2026-06-13T00:49:57'
---

# plugins/installed/bookvault/tests/test_shipping_adapter.py

Symbols in `plugins/installed/bookvault/tests/test_shipping_adapter.py`.

- L20 `_seed_bv_config()` (function)
- L36 `CarrierBookvaultAdapterTests` (class) — _bookvault_quote returns the cheapest BV service as Money,
- L40 `setUp(self)` (method)
- L54 `_fake_cart(self, *, isbn: str | None='9781234567890', country='GB', postcode='SW1A 1AA')` (method) — Build a minimal cart-shaped object _bookvault_quote can read.
- L87 `test_returns_cheapest_service(self)` (method)
- L105 `test_no_isbn_lines_returns_none(self)` (method)
- L119 `test_no_cart_returns_none(self)` (method)
