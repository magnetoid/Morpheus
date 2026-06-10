---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-09T21:57:00'
updated: '2026-06-09T21:57:00'
---

# core/assistant/codegen.py

Symbols in `core/assistant/codegen.py`.

- L41 `_finding(severity, code, message)` (function)
- L45 `_imported_top_levels(tree)` (function)
- L56 `_import_resolves(top: str)` (function)
- L65 `scan_source(source: str, *, kind: str='tool')` (function) — Return a list of findings (possibly empty). Pure static analysis.
- L134 `_const_str(node)` (function)
- L138 `_dict_str_keys(node)` (function) — {str-key: value-node} for an ast.Dict literal (non-string keys skipped).
- L148 `_shape_findings(tree)` (function) — Objective, execution-free checks that a tool draft is well-formed: it has a
- L208 `passed(findings: list[dict])` (function) — True when nothing blocking (CRITICAL/HIGH) was found.
