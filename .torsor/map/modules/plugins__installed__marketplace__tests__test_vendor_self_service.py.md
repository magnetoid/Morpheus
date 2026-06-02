---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-02T18:07:52'
updated: '2026-06-02T18:07:52'
---

# plugins/installed/marketplace/tests/test_vendor_self_service.py

Symbols in `plugins/installed/marketplace/tests/test_vendor_self_service.py`.

- L19 `_make_user(email: str, password: str='pw')` (function)
- L26 `_make_vendor(name: str, owner=None, **kwargs)` (function)
- L31 `_make_product(vendor, **kwargs)` (function)
- L46 `VendorProductsListPermissionTests` (class) — Triplet: anon → login redirect, customer-without-vendor →
- L50 `setUp(self)` (method)
- L63 `test_anon_redirects_to_login(self)` (method)
- L69 `test_customer_without_vendor_sees_empty_state(self)` (method)
- L81 `test_vendor_sees_only_own_products(self)` (method)
- L91 `VendorProductEditPermissionTests` (class) — Triplet for the edit endpoint: anon → login, wrong vendor → 404
- L97 `setUp(self)` (method)
- L112 `_url(self, product_id)` (method)
- L115 `test_anon_redirects(self)` (method)
- L120 `test_non_vendor_user_gets_403(self)` (method)
- L126 `test_other_vendor_cannot_edit(self)` (method) — The attacker IS an approved vendor (so they get past the 403),
- L134 `test_other_vendor_cannot_post_either(self)` (method) — The double-check at fetch time means even a POST is blocked.
- L150 `test_owner_can_view_form(self)` (method)
- L157 `test_owner_can_save_changes(self)` (method)
- L172 `test_invalid_price_doesnt_save(self)` (method)
