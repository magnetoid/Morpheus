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

# core/brain/signals.py

Symbols in `core/brain/signals.py`.

- L21 `plugins_health()` (function)
- L51 `_si_signals(source: str, limit: int=15)` (function) — Recent self-improvement signals of one source (error_log, code_quality…).
- L75 `errors_signal()` (function) — Recent error-log signals the immune system captured.
- L89 `code_signal()` (function) — Code-quality findings + AI recommendations + tracked drift.
- L118 `_setup_signal()` (function) — Core-owned slice of the Improvements section: the first-run setup
- L131 `_gather_all_uncached()` (function) — Everything the Brain knows, in one (DB-heavy) pass.
- L153 `gather_all()` (function) — Cached signal snapshot — ~18 DB queries collapse to one cache hit on a hot
- L165 `invalidate_signals_cache()` (function)
