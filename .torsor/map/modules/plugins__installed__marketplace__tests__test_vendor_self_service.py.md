---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:58'
updated: '2026-06-13T00:49:58'
---

# plugins/installed/marketplace/tests/test_vendor_self_service.py

Symbols in `plugins/installed/marketplace/tests/test_vendor_self_service.py`.

- L20 `_make_user(email: str, password: str='pw')` (function)
- L29 `_make_vendor(name: str, owner=None, **kwargs)` (function)
- L34 `_make_product(vendor, **kwargs)` (function)
- L49 `VendorProductsListPermissionTests` (class) — Triplet: anon → login redirect, customer-without-vendor →
- L53 `setUp(self)` (method)
- L68 `test_anon_redirects_to_login(self)` (method)
- L74 `test_customer_without_vendor_sees_empty_state(self)` (method)
- L86 `test_vendor_sees_only_own_products(self)` (method)
- L96 `VendorProductEditPermissionTests` (class) — Triplet for the edit endpoint: anon → login, wrong vendor → 404
- L102 `setUp(self)` (method)
- L116 `_url(self, product_id)` (method)
- L119 `test_anon_redirects(self)` (method)
- L124 `test_non_vendor_user_gets_403(self)` (method)
- L130 `test_other_vendor_cannot_edit(self)` (method) — The attacker IS an approved vendor (so they get past the 403),
- L138 `test_other_vendor_cannot_post_either(self)` (method) — The double-check at fetch time means even a POST is blocked.
- L157 `test_owner_can_view_form(self)` (method)
- L164 `test_owner_can_save_changes(self)` (method)
- L182 `test_invalid_price_doesnt_save(self)` (method)
