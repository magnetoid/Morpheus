---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-09T21:57:01'
updated: '2026-06-09T21:57:01'
---

# core/db_router.py

Symbols in `core/db_router.py`.

- L3 `PrimaryReplicaRouter` (class) — Database router for Enterprise scale Morpheus.
- L10 `db_for_read(self, model, **hints)` (method) — Reads go to a randomly selected replica, if available.
- L20 `db_for_write(self, model, **hints)` (method) — Writes always go to the primary database.
- L26 `allow_relation(self, obj1, obj2, **hints)` (method) — Relations between objects are allowed if they are both in primary/replica pool.
- L35 `allow_migrate(self, db, app_label, model_name=None, **hints)` (method) — Migrations are only ever applied to the primary database.
