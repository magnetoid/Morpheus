---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-10T20:08:49'
updated: '2026-06-10T20:08:49'
---

# core/updates.py

Symbols in `core/updates.py`.

- L24 `_git(args: list[str], cwd: Path, timeout: int=10)` (function)
- L41 `_git_ok(args: list[str], cwd: Path, timeout: int=10)` (function) — Run git for its exit code only (e.g. merge-base --is-ancestor).
- L57 `_repo_root()` (function)
- L63 `platform_update_status(*, fetch: bool=False)` (function) — Compare the deployed git checkout against its upstream.
- L102 `apply_platform_update(*, confirm: bool=False, run_migrations: bool=True)` (function) — Fast-forward the deployed checkout to its upstream — phase 4.
