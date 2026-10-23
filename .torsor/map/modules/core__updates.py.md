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

# core/updates.py

Symbols in `core/updates.py`.

- L30 `_git(args: list[str], cwd: Path, timeout: int=10)` (function)
- L47 `_git_ok(args: list[str], cwd: Path, timeout: int=10)` (function) — Run git for its exit code only (e.g. merge-base --is-ancestor).
- L63 `_repo_root()` (function)
- L69 `can_self_update()` (function) — True when this install can update its own code: a git checkout with git installed.
- L80 `platform_update_status(*, fetch: bool=False)` (function) — Compare the deployed git checkout against its upstream.
- L135 `refresh_update_status()` (function) — Fetch the live update status (network) and cache it. Called by the
- L155 `cached_update_status()` (function) — Last cached update status (from the daily check), or None if the check
- L163 `_dependency_changes(root: Path, upstream: str)` (function) — Dependency-manifest files that differ between HEAD and upstream. A
- L171 `_boot_probe(root: Path)` (function) — Run ``manage.py check`` in a FRESH interpreter so the *new* (post-merge)
- L191 `apply_platform_update(*, confirm: bool=False, run_migrations: bool=True, allow_dependency_changes: bool=False)` (function) — Fast-forward the deployed checkout to its upstream — phase 4.
