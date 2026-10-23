---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:49'
updated: '2026-10-23T04:51:49'
rules: []
---

# core/tests/test_removed_apps.py

Symbols in `core/tests/test_removed_apps.py`.

- L38 `RemovedAppsTests` (class)
- L39 `test_the_removed_apps_are_not_installed(self)` (method)
- L45 `test_their_code_is_gone(self)` (method)
- L53 `_experiments_as_left()` (function) — The experiments tables as v0.121.0 left them, cut to the columns that tell its seed.
- L74 `LeftoverTablesMigrationTests` (class) — plugins 0002 on an install that ran the experiments app's own migrations, which
- L78 `setUp(self)` (method)
- L85 `_remove(self)` (method)
- L93 `_seed(self, status='draft')` (method)
- L98 `_migrate(self)` (method)
- L107 `test_the_untouched_seed_does_not_keep_the_table(self)` (method)
- L112 `test_a_seed_someone_started_is_kept(self)` (method)
- L118 `test_a_seed_shown_to_visitors_is_kept(self)` (method)
- L132 `SaveForLaterTablesTests` (class) — plugins 0003 on a store as v0.123.0 left it: save_for_later's three tables, its
- L136 `setUp(self)` (method)
- L151 `_remove(self)` (method)
- L158 `test_its_tables_migration_row_and_switch_go(self)` (method)
