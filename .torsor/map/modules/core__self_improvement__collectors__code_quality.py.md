---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-10T20:08:49'
updated: '2026-06-10T20:08:49'
---

# core/self_improvement/collectors/code_quality.py

Symbols in `core/self_improvement/collectors/code_quality.py`.

- L58 `CodeQualityCollector` (class)
- L61 `__init__(self, repo_root: Path | None=None)` (method)
- L64 `run(self)` (method)
- L70 `_run_ruff(self)` (method)
- L97 `_run_bandit(self)` (method)
- L141 `_run_json_command(self, cmd: list[str], *, allow_nonzero: bool=True)` (method) — Run cmd, parse stdout as JSON. Returns ``None`` on parse
- L180 `_relative_path(self, abs_path: str)` (method) — Strip the repo root so paths read as `core/...` not
- L191 `_severity_for_ruff(code: str)` (method)
