---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:57'
updated: '2026-06-13T00:49:57'
---

# core/workflows.py

Symbols in `core/workflows.py`.

- L80 `WorkflowError` (class) — Raised when a workflow fails — message describes the failing step.
- L85 `StepResult` (class)
- L94 `CompensationResult` (class)
- L101 `WorkflowResult` (class)
- L111 `failed(self)` (method)
- L115 `duration_ms(self)` (method)
- L119 `_Step` (class) — Wraps a step callable + its optional compensation.
- L122 `__init__(self, fn: Callable, *, name: str)` (method)
- L127 `compensate(self, fn: Callable)` (method) — Decorator: register a compensation for this step. Returns the
- L133 `__call__(self, instance, ctx)` (method)
- L137 `step(*, name: str | None=None)` (function) — Decorator marking a method as a workflow step.
- L151 `Workflow` (class) — Base class for a named multi-step workflow.
- L164 `register(cls, name: str)` (method) — Class decorator — register a workflow class in the global registry.
- L175 `get(cls, name: str)` (method)
- L179 `all_registered(cls)` (method)
- L182 `_discover_steps(self)` (method) — Walk the class MRO + collect _Step instances in declaration order.
- L193 `run(self, ctx: dict[str, Any] | None=None)` (method) — Execute the workflow. Returns a WorkflowResult; never raises.
- L289 `_audit(self, kind: str, step_name: str, ctx: dict, *, error: str)` (method) — Best-effort audit log emission. Failures here are swallowed —
