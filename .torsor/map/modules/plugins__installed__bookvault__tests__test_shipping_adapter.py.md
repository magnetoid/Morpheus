---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-10T20:08:49'
updated: '2026-06-10T20:08:49'
---

# plugins/installed/bookvault/tests/test_shipping_adapter.py

Symbols in `plugins/installed/bookvault/tests/test_shipping_adapter.py`.

- L19 `_seed_bv_config()` (function)
- L32 `CarrierBookvaultAdapterTests` (class) — _bookvault_quote returns the cheapest BV service as Money,
- L36 `setUp(self)` (method)
- L47 `_fake_cart(self, *, isbn: str | None='9781234567890', country='GB', postcode='SW1A 1AA')` (method) — Build a minimal cart-shaped object _bookvault_quote can read.
- L71 `test_returns_cheapest_service(self)` (method)
- L89 `test_no_isbn_lines_returns_none(self)` (method)
- L103 `test_no_cart_returns_none(self)` (method)
