---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-09T21:57:01'
updated: '2026-06-09T21:57:01'
---

# core/safety.py

Symbols in `core/safety.py`.

- L135 `SafetyViolation` (class) — Raised when a proposed change crosses the safety boundary.
- L142 `__init__(self, reasons: Iterable[str])` (method)
- L150 `_compile_path_pattern(pat: str)` (function) — Compile a PROTECTED_PATHS entry to a fullmatch regex.
- L180 `is_path_protected(path: str)` (function) — Return True if `path` falls inside any PROTECTED_PATHS entry.
- L190 `find_violations(diff_text: str, files_touched: Iterable[str]=())` (function) — Return human-readable reasons the diff violates the safety boundary.
- L225 `assert_diff_safe(diff_text: str, files_touched: Iterable[str]=())` (function) — Raise SafetyViolation if the diff crosses the boundary; return None otherwise.
- L241 `is_class_allowed(class_name: str)` (function) — Return True if `class_name` is NOT in the blocklist.
- L246 `is_plugin_protected(plugin_name: str)` (function) — Return True if `plugin_name` cannot be disabled (soft-brick risk).
