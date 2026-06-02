---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-02T18:07:51'
updated: '2026-06-02T18:07:51'
---

# core/workflows.py

Symbols in `core/workflows.py`.

- L78 `WorkflowError` (class) — Raised when a workflow fails — message describes the failing step.
- L83 `StepResult` (class)
- L92 `CompensationResult` (class)
- L99 `WorkflowResult` (class)
- L109 `failed(self)` (method)
- L113 `duration_ms(self)` (method)
- L117 `_Step` (class) — Wraps a step callable + its optional compensation.
- L120 `__init__(self, fn: Callable, *, name: str)` (method)
- L125 `compensate(self, fn: Callable)` (method) — Decorator: register a compensation for this step. Returns the
- L131 `__call__(self, instance, ctx)` (method)
- L135 `step(*, name: str | None=None)` (function) — Decorator marking a method as a workflow step.
- L147 `Workflow` (class) — Base class for a named multi-step workflow.
- L160 `register(cls, name: str)` (method) — Class decorator — register a workflow class in the global registry.
- L169 `get(cls, name: str)` (method)
- L173 `all_registered(cls)` (method)
- L176 `_discover_steps(self)` (method) — Walk the class MRO + collect _Step instances in declaration order.
- L187 `run(self, ctx: dict[str, Any] | None=None)` (method) — Execute the workflow. Returns a WorkflowResult; never raises.
- L261 `_audit(self, kind: str, step_name: str, ctx: dict, *, error: str)` (method) — Best-effort audit log emission. Failures here are swallowed —
