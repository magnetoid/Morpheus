---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:57'
updated: '2026-06-13T00:49:57'
---

# core/self_improvement/services.py

Symbols in `core/self_improvement/services.py`.

- L46 `emit_signal(*, source: str, fingerprint: str, severity: int=50, payload: dict[str, Any] | None=None, occurred_at=None)` (function) — Record one signal, with dedup + suppression baked in.
- L118 `models_either_unexpired_or_after(now)` (function) — Q-object factory: ``expires_at IS NULL`` OR ``expires_at > now``.
- L134 `fingerprint_for(*parts: Any)` (function) — SHA-256 (first 32 hex chars) of the colon-joined parts.
- L149 `start_ingest_job(collector: str)` (function) — Record the start of a collector run. Returns the open job row.
- L158 `finish_ingest_job(job: SiIngestJob, *, signals_emitted: int, status: str='ok', error: str='')` (function) — Stamp finished_at + counts on an open job row.
- L184 `is_path_customized(path: str)` (function) — Return True if `path` has a non-expired SiCustomization row with
