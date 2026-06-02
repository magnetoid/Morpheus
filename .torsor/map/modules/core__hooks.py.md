---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-02T18:07:51'
updated: '2026-06-02T18:07:51'
---

# core/hooks.py

Symbols in `core/hooks.py`.

- L20 `HookRegistry` (class) — Lightweight ordered event bus.
- L35 `__init__(self)` (method)
- L41 `register(self, event: str, handler: Callable, priority: int=50, mode: str='sync')` (method) — Register a handler for an event. Lower priority = runs first.
- L73 `unregister(self, event: str, handler: Callable)` (method) — Remove a handler from an event.
- L77 `fire(self, event: str, **kwargs: Any)` (method) — Fire an event. All registered handlers are called in priority order.
- L117 `_enqueue_async(self, event: str, handler: Callable, kwargs: dict)` (method) — Send a hook-handler invocation to Celery.
- L150 `filter(self, event: str, value: Any, **kwargs: Any)` (method) — Filter an event — each handler receives the (potentially modified) value
- L183 `_serialize_payload(kwargs: dict[str, Any])` (method)
- L218 `_dispatch_remote(self, event: str, kwargs: dict[str, Any])` (method) — Serialize the event payload and dispatch to (a) any subscribed
- L260 `has_handlers(self, event: str)` (method)
- L263 `list_handlers(self, event: str)` (method)
- L270 `clear(self, event: str | None=None)` (method) — Clear handlers. If event is None, clears all.
- L300 `MorpheusEvents` (class) — Catalogue of all built-in hook events.
