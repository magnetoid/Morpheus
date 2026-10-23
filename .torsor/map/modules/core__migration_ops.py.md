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

# core/migration_ops.py

Symbols in `core/migration_ops.py`.

- L22 `DropLeftoverModel` (class)
- L25 `database_forwards(self, app_label, schema_editor, from_state, to_state)` (method)
- L47 `describe(self)` (method)
- L51 `leftover_table_drops(tables: dict[str, str])` (function) — The operations that drop a removed app's leftover tables, for a ``plugins`` app
- L71 `forget_apps(*labels: str)` (function) — A ``RunPython`` function that deletes what ``django_migrations`` and ``PluginConfig``
