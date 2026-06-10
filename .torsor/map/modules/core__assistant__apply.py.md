---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-10T20:08:48'
updated: '2026-06-10T20:08:48'
---

# core/assistant/apply.py

Symbols in `core/assistant/apply.py`.

- L49 `apply_enabled()` (function) — The master kill switch (ADR 0014). Default OFF — the whole apply path is
- L55 `_git(args: list[str], *, stdin: str | None=None, env_extra: dict | None=None, timeout: int=15)` (function) — Run git with fixed args (no shell). Returns (returncode, stdout-or-stderr).
- L77 `_is_git_repo()` (function)
- L81 `_applies_last_24h()` (function)
- L90 `preflight(proposal)` (function) — Return the list of reasons this proposal may NOT be applied. Empty list =
- L136 `_write_branch(proposal, target: str, branch: str)` (function) — Create `branch` as a commit that adds `target`=source on top of HEAD,
- L183 `apply_proposal(proposal)` (function) — Gate → write to a NEW selfdev/* branch (never main) → audit. Never raises.
