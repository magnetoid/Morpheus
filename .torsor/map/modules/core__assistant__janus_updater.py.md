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

# core/assistant/janus_updater.py

Symbols in `core/assistant/janus_updater.py`.

- L45 `_now()` (function)
- L49 `_read(path: Path)` (function)
- L57 `_write(path: Path, data: dict)` (function)
- L63 `latest_commit(repo: str, ref: str)` (function) — ``{sha, title, date}`` of the newest commit on ``ref``. Raises on failure.
- L82 `_env(home: Path)` (function)
- L89 `install(venv: Path, repo: str, sha: str, pins: list[str], home: Path)` (function) — A fresh venv with Janus at ``sha``. Returns (ok, the tail of pip's output).
- L116 `run_contract(venv: Path, contract: Path, home: Path)` (function) — The contract report for the Janus in ``venv`` (``ok`` False when it can't run).
- L134 `_failed_checks(report: dict)` (function)
- L143 `_prune(root: Path, keep: set[str])` (function)
- L153 `_lock(root: Path)` (function)
- L166 `update(args: argparse.Namespace)` (function) — One check. Returns the result recorded in ``state.json['last_check']``.
- L224 `_args(argv: list[str])` (function)
- L242 `main(argv: list[str] | None=None)` (function)
