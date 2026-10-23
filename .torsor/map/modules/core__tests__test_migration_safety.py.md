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

# core/tests/test_migration_safety.py

Symbols in `core/tests/test_migration_safety.py`.

- L16 `_state()` (function)
- L33 `_migration(*operations, **attrs)` (function)
- L41 `UnsafeOperationTests` (class)
- L42 `assert_blocks(self, operation, word)` (method)
- L48 `test_removing_a_field(self)` (method)
- L51 `test_deleting_a_model(self)` (method)
- L54 `test_renaming_a_field(self)` (method)
- L59 `test_renaming_a_model(self)` (method)
- L62 `test_renaming_a_table(self)` (method)
- L65 `test_raw_sql(self)` (method)
- L68 `test_a_not_null_field_without_a_database_default(self)` (method)
- L72 `test_a_nullable_column_made_not_null_even_with_a_default(self)` (method)
- L77 `SafeOperationTests` (class)
- L78 `assert_passes(self, *operations)` (method)
- L83 `test_a_nullable_field(self)` (method)
- L86 `test_a_not_null_field_with_a_database_default(self)` (method)
- L90 `test_a_many_to_many_field(self)` (method)
- L93 `test_a_new_model(self)` (method)
- L98 `test_a_not_null_column_that_was_already_not_null(self)` (method)
- L101 `test_a_column_made_nullable(self)` (method)
- L105 `test_python_data_changes(self)` (method)
- L109 `SeparateStateTests` (class)
- L110 `test_state_only_operations_are_not_flagged(self)` (method)
- L116 `test_a_database_operation_inside_separate_state_is_reviewed(self)` (method)
- L123 `ContractTests` (class)
- L124 `test_a_contract_accepts_the_migration(self)` (method)
- L133 `test_a_blank_contract_does_not_count(self)` (method)
- L140 `test_a_squashed_migration_is_not_reviewed(self)` (method)
- L150 `NewTableTests` (class) — The previous release has no table this release creates, so nothing done to
- L154 `test_changes_to_a_table_created_in_the_same_migration_are_not_flagged(self)` (method)
- L164 `test_a_table_created_earlier_in_the_release_is_new(self)` (method)
- L175 `test_a_state_only_create_model_is_not_a_new_table(self)` (method)
- L190 `test_an_existing_table_next_to_a_new_one_is_still_checked(self)` (method)
- L202 `OrderTests` (class)
- L203 `test_operations_are_judged_in_order(self)` (method)
- L216 `test_the_callers_state_is_left_alone(self)` (method)
