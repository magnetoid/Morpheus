---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:50'
updated: '2026-10-23T04:51:50'
rules: []
---

# plugins/installed/book_product/tests/test_disable_vertical.py

Symbols in `plugins/installed/book_product/tests/test_disable_vertical.py`.

- L32 `_app_list(**env_overrides)` (function) — The real ALL_MORPHEUS_APPS a deployment would boot with, assembled by
- L45 `DisabledAppsMechanismTests` (class)
- L46 `test_a_store_that_disables_the_vertical_loses_exactly_it(self)` (method)
- L60 `test_a_store_that_sets_nothing_keeps_the_vertical(self)` (method) — dotbooks: no disable env -> book_product and its bundle stay.
- L67 `test_disabling_a_non_default_app_is_a_no_op_not_a_crash(self)` (method)
- L71 `test_an_app_in_both_default_and_extra_is_not_double_registered(self)` (method)
- L76 `BookNavIsContributedNotHardcodedTests` (class) — The move that makes a disable clean: if these ever go back into
- L81 `test_book_product_context_processors_are_not_in_settings_templates(self)` (method)
- L89 `test_book_product_registers_its_nav_processors(self)` (method)
- L98 `SharedCardSurvivesBookDisableTests` (class) — The shared storefront product card renders on stores with the book
- L105 `test_no_theme_product_card_loads_book_extras(self)` (method)
