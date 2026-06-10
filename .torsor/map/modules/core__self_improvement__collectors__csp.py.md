---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-09T21:57:01'
updated: '2026-06-09T21:57:01'
---

# core/self_improvement/collectors/csp.py

Symbols in `core/self_improvement/collectors/csp.py`.

- L27 `_normalise_uri(uri: str)` (function) — Strip path/query so different paths under the same origin dedup.
- L40 `on_csp_violation_reported(*, directive: str='', blocked_uri: str='', document_uri: str='', line: Any=None, source_file: str='', **_: Any)` (function) — Hook handler — kwargs match what api/views.csp_report fires.
- L76 `_severity_for(directive: str, blocked: str)` (function) — Heuristic severity. script-src violations are higher than style-src
