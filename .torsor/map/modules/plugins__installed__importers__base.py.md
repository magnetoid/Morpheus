---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-02T18:07:52'
updated: '2026-06-02T18:07:52'
---

# plugins/installed/importers/base.py

Symbols in `plugins/installed/importers/base.py`.

- L28 `ImportSummary` (class)
- L32 `increment(self, key: str, n: int=1)` (method)
- L36 `BaseImporter` (class) — Subclass and implement `iter_*` methods + `run`.
- L41 `__init__(self)` (method)
- L48 `run(self, *, started_by: str='')` (method) — Top-level entry point. Subclasses can override for custom orchestration.
- L79 `_run(self)` (method)
- L84 `upsert(self, *, source_id: str, dest_obj, metadata: Mapping[str, Any] | None=None)` (method) — Idempotent: link a source_id to a Morpheus model instance.
- L105 `find_existing(self, *, source_id: str, dest_model: str)` (method)
