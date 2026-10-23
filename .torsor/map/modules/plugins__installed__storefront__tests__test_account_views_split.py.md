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

# plugins/installed/storefront/tests/test_account_views_split.py

Symbols in `plugins/installed/storefront/tests/test_account_views_split.py`.

- L11 `AccountViewsSplitTests` (class) — Make sure the views/ package split didn't break the auth gates
- L17 `setUp(self)` (method)
- L20 `test_views_module_still_imports(self)` (method) — URL conf imports `from . import views`; that has to work.
- L46 `test_account_home_anon_redirects(self)` (method)
- L51 `test_account_orders_anon_redirects(self)` (method)
- L56 `test_account_credits_anon_redirects(self)` (method)
- L61 `test_account_downloads_anon_redirects(self)` (method)
- L66 `test_account_home_authed_200(self)` (method)
