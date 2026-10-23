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

# plugins/installed/seo/tests/test_seo_authz.py

Symbols in `plugins/installed/seo/tests/test_seo_authz.py`.

- L37 `_set_mode(mode: str)` (function)
- L45 `SeoDashboardBoundaryTests` (class)
- L47 `setUpTestData(cls)` (method)
- L65 `setUp(self)` (method)
- L72 `test_anonymous_is_sent_to_login(self)` (method)
- L77 `test_a_signed_in_shopper_gets_nowhere(self)` (method)
- L82 `test_staff_without_the_capability_is_refused_every_read_surface(self)` (method) — The gap this closes: `is_staff` alone used to be the whole check.
- L89 `test_a_marketing_manager_may_read_every_surface(self)` (method)
- L95 `_become_read_only(self)` (method) — A staff user holding seo.read and nothing else.
- L108 `test_every_page_that_reads_and_writes_refuses_the_write(self)` (method) — Each page below serves a list on GET and a mutation on POST from one
- L150 `test_the_404_page_does_not_write_on_a_read(self)` (method) — Suggesting targets stores `suggested_target`; it used to run on every
