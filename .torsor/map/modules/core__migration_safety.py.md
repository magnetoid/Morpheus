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

# core/migration_safety.py

Symbols in `core/migration_safety.py`.

- L49 `Review` (class)
- L55 `blocks(self)` (method)
- L59 `review(migration, state_before, new_models=None)` (function) — What in ``migration`` the previous release would trip over, given the
- L76 `_findings(app_label, operations, state, new_models)` (function)
- L92 `_model_of(op)` (function)
- L98 `_finding(app_label, op, state)` (function)
- L137 `_not_null_without_db_default(field)` (function)
- L143 `_becomes_not_null(app_label, op, state)` (function)
- L151 `review_files(base_dir: Path, paths: list[str])` (function) — Review the migration files at ``paths`` (relative to ``base_dir``), as Django
