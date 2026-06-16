---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:57'
updated: '2026-06-13T00:49:57'
---

# core/agents/sandbox.py

Symbols in `core/agents/sandbox.py`.

- L38 `SandboxError` (class) — Raised on validation failure, timeout, or in-script error.
- L110 `_validate(tree: ast.AST)` (function)
- L128 `run_sandboxed(source: str, *, extra_globals: dict[str, Any] | None=None, timeout_ms: int=DEFAULT_TIMEOUT_MS)` (function) — Execute ``source`` in the sandbox and return its ``result`` variable.
