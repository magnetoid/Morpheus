---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:58'
updated: '2026-06-13T00:49:58'
---

# plugins/installed/functions/runtime.py

Symbols in `plugins/installed/functions/runtime.py`.

- L72 `register_capability(name: str, exports: Mapping[str, Any])` (function) — Plugin-author hook to add a capability set.
- L77 `resolve_capabilities(names: list[str])` (function)
- L91 `FunctionError` (class) — Raised on configuration / capability errors (NOT user-code errors).
- L95 `FunctionExecutionError` (class) — Raised when user code raises or times out.
- L136 `_validate_ast(tree: ast.AST)` (function)
- L185 `FunctionResult` (class)
- L190 `_compile_function(source: str)` (function) — Parse + AST-check + compile a function body.
- L205 `_run_in_thread(target, args, timeout_seconds: float)` (function) — Run `target(*args)` on a worker thread; return result or raise on timeout.
- L229 `execute(*, source: str, input: Mapping[str, Any] | None=None, capabilities: list[str] | None=None, timeout_ms: int=200)` (function) — Compile and run a Function source against `input`, returning `run(input)`.
