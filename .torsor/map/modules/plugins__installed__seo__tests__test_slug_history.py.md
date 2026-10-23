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

# plugins/installed/seo/tests/test_slug_history.py

Symbols in `plugins/installed/seo/tests/test_slug_history.py`.

- L21 `_product(slug: str)` (function)
- L31 `SlugHistoryTests` (class)
- L32 `setUp(self)` (method)
- L35 `test_renaming_a_product_mints_a_301_from_the_old_url(self)` (method)
- L43 `test_the_history_row_is_kept_even_when_auto_redirects_are_off(self)` (method) — One row is cheap, and it is what later lets the 404 suggester answer
- L54 `test_a_hand_written_rule_is_never_overwritten(self)` (method) — A merchant may have deliberately sent the old URL somewhere other
- L66 `test_renaming_twice_does_not_leave_a_chain(self)` (method)
- L76 `test_saving_without_changing_the_slug_creates_nothing(self)` (method)
- L84 `test_the_404_suggester_prefers_a_known_former_url(self)` (method)
