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

# core/tests/test_migration_ops.py

Symbols in `core/tests/test_migration_ops.py`.

- L24 `_state()` (function)
- L34 `DropLeftoverModelTests` (class)
- L35 `_create(self, rows=0)` (method)
- L43 `_remove(self)` (method)
- L48 `_run(self)` (method)
- L56 `test_an_empty_leftover_table_is_dropped(self)` (method)
- L61 `test_a_table_that_is_not_there_is_left_alone(self)` (method)
- L66 `test_a_table_with_rows_is_kept(self)` (method)
- L72 `test_the_migration_gate_asks_for_a_contract(self)` (method)
- L78 `test_leftover_table_drops_drop_a_table_that_is_there_and_empty(self)` (method)
- L89 `test_the_gate_sees_every_drop_leftover_table_drops_makes(self)` (method)
- L99 `_linked_state(*, child=True)` (function)
- L115 `KeptLeftoverForeignKeyTests` (class) — Once its model is gone, nothing deletes a kept table's rows before what they point
- L119 `_remove(self)` (method)
- L127 `test_what_a_kept_row_points_at_can_still_be_deleted(self)` (method)
- L153 `ForgetAppsTests` (class) — forget_apps: an app that left the code leaves no migration history or switch behind,
- L157 `test_only_the_named_apps_are_forgotten(self)` (method)
- L173 `test_the_gate_sees_forget_apps(self)` (method)
