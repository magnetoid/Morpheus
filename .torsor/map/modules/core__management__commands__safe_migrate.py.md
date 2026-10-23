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

# core/management/commands/safe_migrate.py

Symbols in `core/management/commands/safe_migrate.py`.

- L28 `Command` (class)
- L32 `handle(self, *args, **options)` (method)
- L44 `_back_up_first(self)` (method)
- L82 `_migrate(self)` (method)
- L86 `_record(self, *, final: bool)` (method) — Record this deploy; False when it cannot be written yet. Before
- L110 `_tell_rollback(self)` (method) — Email the operators that the store went back to an older release. Last,
