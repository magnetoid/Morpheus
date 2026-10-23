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

# core/assistant/janus_runtime.py

Symbols in `core/assistant/janus_runtime.py`.

- L76 `_settings()` (function)
- L82 `engine_dir()` (function)
- L88 `_read_json(path: Path)` (function)
- L96 `_write_json(path: Path, data: dict)` (function)
- L102 `state()` (function)
- L111 `venv_of(janus_bin: str | None)` (function) — The venv a ``janus`` executable belongs to (follows the /usr/local/bin link).
- L119 `installed_build(janus_bin: str | None)` (function) — Version, commit, ref and repository of a Janus install; '' where unknown.
- L156 `contract_report(janus_bin: str | None)` (function) — The contract report recorded when this Janus was installed, or {}.
- L162 `image_bin()` (function) — The Janus the image installed (``janus`` on PATH), ignoring auto-installs.
- L170 `enabled()` (function) — Deployment switch (``LINDA_JANUS_AUTO_UPDATE``) and the merchant's, both on.
- L179 `active_bin()` (function) — The verified auto-installed ``janus`` to run, or None to use the image's.
- L198 `source()` (function) — Where updates come from: the image's repository and branch, or None to freeze.
- L206 `_last_attempt(root: Path)` (function)
- L215 `maybe_update(*, force: bool=False)` (function) — Start the updater in the background when a check is due. Never blocks.
- L235 `_spawn_updater(root: Path, origin: dict, *, force: bool)` (function)
- L282 `record_turn(*, error: str='')` (function) — Count engine failures on an auto-installed Janus; put the previous one back
- L304 `_roll_back(current: dict, error: str)` (function)
- L323 `_locked(root: Path)` (function)
- L337 `summary()` (function) — What the Janus page shows about updates.
