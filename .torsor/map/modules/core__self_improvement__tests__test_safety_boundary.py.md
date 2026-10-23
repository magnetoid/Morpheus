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
- L189 `test_file_limit_flagged_for_generator_input(self)` (method)
- L204 `TestClassBlocklist` (class)
- L206 `test_blocked_class_refused(self, blocked: str)` (method)
- L213 `test_allowed_class_passes(self, allowed: str)` (method)
- L222 `TestPluginProtection` (class)
- L224 `test_protected_plugin(self, protected: str)` (method)
- L230 `test_togglable_plugin(self, togglable: str)` (method)
- L239 `TestAssertDiffSafe` (class)
- L240 `test_safe_diff_passes(self)` (method)
- L247 `test_protected_path_raises(self)` (method)
- L252 `test_forbidden_pattern_raises(self)` (method)
- L257 `test_multiple_reasons_all_listed(self)` (method)
- L274 `TestBoundaryInvariants` (class) — If someone deletes a PROTECTED_PATHS entry, these tests notice.
- L277 `test_payments_protected(self)` (method)
- L280 `test_auth_protected(self)` (method)
- L285 `test_migrations_protected(self)` (method)
- L288 `test_engine_self_protected(self)` (method)
- L292 `test_no_forbidden_patterns_removed(self)` (method)
- L308 `TestExtraProtectedPaths` (class) — settings.SELF_IMPROVEMENT['extra_protected_paths'] extends (never
- L312 `test_extra_paths_are_honored(self)` (method)
- L325 `test_static_boundary_unaffected_by_settings(self)` (method)
- L334 `TestPrecommitSubset` (class) — PRECOMMIT_FORBIDDEN_PATTERNS — the human-applicable subset enforced
- L338 `test_catches_hardcoded_secrets_and_destructive_sql(self)` (method)
- L358 `test_precommit_script_parses_added_lines(self)` (method)
