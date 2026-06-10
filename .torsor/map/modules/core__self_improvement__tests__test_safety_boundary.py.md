---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-09T21:57:01'
updated: '2026-06-09T21:57:01'
---

# core/self_improvement/tests/test_safety_boundary.py

Symbols in `core/self_improvement/tests/test_safety_boundary.py`.

- L43 `TestProtectedPaths` (class) — Every entry in PROTECTED_PATHS must produce True for at least one
- L95 `test_path_is_rejected(self, path: str)` (method)
- L99 `TestAllowedPaths` (class) — Paths that should slip past the boundary so legitimate AI proposals
- L124 `test_path_is_allowed(self, path: str)` (method)
- L133 `TestForbiddenDiffPatterns` (class) — Every FORBIDDEN_DIFF_PATTERNS entry must catch at least one
- L159 `test_pattern_is_flagged(self, diff: str, expected_substr: str)` (method)
- L171 `TestMagnitudeLimits` (class)
- L172 `test_line_limit_flagged(self)` (method)
- L177 `test_file_limit_flagged(self)` (method)
- L184 `test_small_diff_passes(self)` (method)
- L195 `TestClassBlocklist` (class)
- L197 `test_blocked_class_refused(self, blocked: str)` (method)
- L204 `test_allowed_class_passes(self, allowed: str)` (method)
- L213 `TestPluginProtection` (class)
- L215 `test_protected_plugin(self, protected: str)` (method)
- L221 `test_togglable_plugin(self, togglable: str)` (method)
- L230 `TestAssertDiffSafe` (class)
- L231 `test_safe_diff_passes(self)` (method)
- L238 `test_protected_path_raises(self)` (method)
- L243 `test_forbidden_pattern_raises(self)` (method)
- L248 `test_multiple_reasons_all_listed(self)` (method)
- L265 `TestBoundaryInvariants` (class) — If someone deletes a PROTECTED_PATHS entry, these tests notice.
- L268 `test_payments_protected(self)` (method)
- L271 `test_auth_protected(self)` (method)
- L276 `test_migrations_protected(self)` (method)
- L279 `test_engine_self_protected(self)` (method)
- L283 `test_no_forbidden_patterns_removed(self)` (method)
