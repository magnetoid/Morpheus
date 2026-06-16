---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:57'
updated: '2026-06-13T00:49:57'
---

# core/circuit_breaker.py

Symbols in `core/circuit_breaker.py`.

- L61 `CircuitOpenError` (class) — Raised when a circuit is OPEN and a call would otherwise be made.
- L66 `_BreakerState` (class)
- L72 `CircuitBreaker` (class) — Reusable, named circuit breaker.
- L86 `__init__(self, *, name: str, failure_threshold: int=5, cooldown_seconds: float=30.0, expected_exceptions: tuple[type[BaseException], ...]=(Exception,))` (method)
- L104 `get(cls, name: str)` (method)
- L108 `snapshot(cls)` (method) — Return a JSON-serialisable list of every breaker's current state.
- L129 `state_label(self)` (method)
- L138 `__enter__(self)` (method)
- L147 `__exit__(self, exc_type, exc, tb)` (method)
- L158 `__call__(self, fn: Callable[..., Any])` (method)
- L168 `_record_success(self)` (method)
- L179 `_record_failure(self, exc: BaseException)` (method)
- L197 `reset(self)` (method) — Manually reset to CLOSED. Used by ops tooling + tests.
