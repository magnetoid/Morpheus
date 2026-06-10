---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-09T21:57:01'
updated: '2026-06-09T21:57:01'
---

# core/circuit_breaker.py

Symbols in `core/circuit_breaker.py`.

- L59 `CircuitOpenError` (class) — Raised when a circuit is OPEN and a call would otherwise be made.
- L64 `_BreakerState` (class)
- L70 `CircuitBreaker` (class) — Reusable, named circuit breaker.
- L84 `__init__(self, *, name: str, failure_threshold: int=5, cooldown_seconds: float=30.0, expected_exceptions: tuple[type[BaseException], ...]=(Exception,))` (method)
- L102 `get(cls, name: str)` (method)
- L106 `snapshot(cls)` (method) — Return a JSON-serialisable list of every breaker's current state.
- L126 `state_label(self)` (method)
- L135 `__enter__(self)` (method)
- L144 `__exit__(self, exc_type, exc, tb)` (method)
- L155 `__call__(self, fn: Callable[..., Any])` (method)
- L164 `_record_success(self)` (method)
- L174 `_record_failure(self, exc: BaseException)` (method)
- L190 `reset(self)` (method) — Manually reset to CLOSED. Used by ops tooling + tests.
