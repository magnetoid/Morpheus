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

# core/safety.py

Symbols in `core/safety.py`.

- L173 `SafetyViolation` (class) — Raised when a proposed change crosses the safety boundary.
- L180 `__init__(self, reasons: Iterable[str])` (method)
- L188 `_compile_path_pattern(pat: str)` (function) — Compile a PROTECTED_PATHS entry to a fullmatch regex.
- L231 `_extra_protected_patterns()` (function)
- L247 `is_path_protected(path: str)` (function) — Return True if `path` falls inside any PROTECTED_PATHS entry
- L260 `find_violations(diff_text: str, files_touched: Iterable[str]=())` (function) — Return human-readable reasons the diff violates the safety boundary.
- L300 `assert_diff_safe(diff_text: str, files_touched: Iterable[str]=())` (function) — Raise SafetyViolation if the diff crosses the boundary; return None otherwise.
- L319 `is_class_allowed(class_name: str)` (function) — Return True if `class_name` is NOT in the blocklist.
- L324 `is_plugin_protected(plugin_name: str)` (function) — Return True if `plugin_name` cannot be disabled (soft-brick risk).
