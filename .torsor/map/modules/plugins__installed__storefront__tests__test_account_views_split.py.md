---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-02T18:07:53'
updated: '2026-06-02T18:07:53'
---

# plugins/installed/storefront/tests/test_account_views_split.py

Symbols in `plugins/installed/storefront/tests/test_account_views_split.py`.

- L10 `AccountViewsSplitTests` (class) — Make sure the views/ package split didn't break the auth gates
- L16 `setUp(self)` (method)
- L19 `test_views_module_still_imports(self)` (method) — URL conf imports `from . import views`; that has to work.
- L33 `test_account_home_anon_redirects(self)` (method)
- L38 `test_account_orders_anon_redirects(self)` (method)
- L43 `test_account_credits_anon_redirects(self)` (method)
- L48 `test_account_downloads_anon_redirects(self)` (method)
- L53 `test_account_home_authed_200(self)` (method)
