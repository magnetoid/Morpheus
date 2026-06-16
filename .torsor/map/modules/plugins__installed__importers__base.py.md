---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:58'
updated: '2026-06-13T00:49:58'
---

# plugins/installed/importers/base.py

Symbols in `plugins/installed/importers/base.py`.

- L30 `ImportSummary` (class)
- L34 `increment(self, key: str, n: int=1)` (method)
- L38 `BaseImporter` (class) — Subclass and implement `iter_*` methods + `run`.
- L43 `__init__(self)` (method)
- L50 `run(self, *, started_by: str='')` (method) — Top-level entry point. Subclasses can override for custom orchestration.
- L81 `_run(self)` (method)
- L86 `upsert(self, *, source_id: str, dest_obj, metadata: Mapping[str, Any] | None=None)` (method) — Idempotent: link a source_id to a Morpheus model instance.
- L107 `find_existing(self, *, source_id: str, dest_model: str)` (method)
