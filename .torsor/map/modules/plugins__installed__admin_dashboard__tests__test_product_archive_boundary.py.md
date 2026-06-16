---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:57'
updated: '2026-06-13T00:49:57'
---

# plugins/installed/admin_dashboard/tests/test_product_archive_boundary.py

Symbols in `plugins/installed/admin_dashboard/tests/test_product_archive_boundary.py`.

- L29 `_make_user(email: str, *, is_staff: bool=False)` (function)
- L39 `_make_product(**kwargs)` (function)
- L52 `ProductArchiveBoundaryTests` (class)
- L53 `setUp(self)` (method)
- L60 `test_anonymous_redirected_to_login_and_no_mutation(self)` (method)
- L67 `test_authed_without_staff_blocked_and_no_mutation(self)` (method)
- L74 `test_staff_allowed_and_status_toggles(self)` (method)
