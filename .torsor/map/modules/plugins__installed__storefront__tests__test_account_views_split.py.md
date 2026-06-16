---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:58'
updated: '2026-06-13T00:49:58'
---

# plugins/installed/storefront/tests/test_account_views_split.py

Symbols in `plugins/installed/storefront/tests/test_account_views_split.py`.

- L11 `AccountViewsSplitTests` (class) — Make sure the views/ package split didn't break the auth gates
- L17 `setUp(self)` (method)
- L20 `test_views_module_still_imports(self)` (method) — URL conf imports `from . import views`; that has to work.
- L43 `test_account_home_anon_redirects(self)` (method)
- L48 `test_account_orders_anon_redirects(self)` (method)
- L53 `test_account_credits_anon_redirects(self)` (method)
- L58 `test_account_downloads_anon_redirects(self)` (method)
- L63 `test_account_home_authed_200(self)` (method)
