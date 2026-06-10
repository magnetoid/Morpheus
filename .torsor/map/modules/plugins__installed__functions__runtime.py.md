---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-10T20:08:50'
updated: '2026-06-10T20:08:50'
---

# plugins/installed/functions/runtime.py

Symbols in `plugins/installed/functions/runtime.py`.

- L70 `register_capability(name: str, exports: Mapping[str, Any])` (function) — Plugin-author hook to add a capability set.
- L75 `resolve_capabilities(names: list[str])` (function)
- L89 `FunctionError` (class) — Raised on configuration / capability errors (NOT user-code errors).
- L93 `FunctionExecutionError` (class) — Raised when user code raises or times out.
- L126 `_validate_ast(tree: ast.AST)` (function)
- L175 `FunctionResult` (class)
- L180 `_compile_function(source: str)` (function) — Parse + AST-check + compile a function body.
- L195 `_run_in_thread(target, args, timeout_seconds: float)` (function) — Run `target(*args)` on a worker thread; return result or raise on timeout.
- L219 `execute(*, source: str, input: Mapping[str, Any] | None=None, capabilities: list[str] | None=None, timeout_ms: int=200)` (function) — Compile and run a Function source against `input`, returning `run(input)`.
