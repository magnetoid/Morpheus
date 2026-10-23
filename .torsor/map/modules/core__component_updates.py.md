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

# core/component_updates.py

Symbols in `core/component_updates.py`.

- L78 `ArtifactError` (class) — The artifact could not be trusted or unpacked. Never leaves files behind.
- L85 `fetch_artifact(url: str, sha256: str, dest_dir: Path, *, max_bytes: int=_MAX_ARTIFACT_BYTES)` (function) — Download `url` into `dest_dir` and return the path — only if its SHA-256
- L145 `_member_top(name: str)` (function)
- L149 `inspect_archive(archive: Path)` (function) — Validate every member and return the single top-level directory name.
- L195 `extract_component(archive: Path, staging: Path, kind: str, name: str)` (function) — Unpack `archive` to `staging/<name>` and return that path.
- L235 `_repo_root()` (function)
- L241 `component_dir(kind: str, name: str)` (function) — Directory of the installed component, resolved from the loaded module —
- L269 `_ships_with_core(kind: str, name: str, path: Path)` (function) — Reason this component must be updated *with core*, or None if it may be
- L298 `_protected(path: Path)` (function) — Everything that mutates installed code consults `core/safety.py`.
- L310 `find_component_release(kind: str, name: str)` (function)
- L320 `apply_component_update(kind: str, name: str, *, confirm: bool=False, run_migrations: bool=True)` (function) — Update one app or theme from the signed manifest. Dry-run by default.
