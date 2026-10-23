---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:49'
updated: '2026-10-23T04:51:49'
rules: []
---

# core/hooks.py

Symbols in `core/hooks.py`.

- L20 `HookRegistry` (class) — Lightweight ordered event bus.
- L35 `__init__(self)` (method)
- L49 `set_active_check(self, fn: Callable[[str], bool])` (method) — Wire the 'is this plugin active?' predicate (plugins.registry.is_active).
- L55 `_unpack(entry: tuple)` (method) — Normalise a handler entry to (priority, handler, mode, plugin),
- L63 `_owner_inactive(self, plugin: str | None)` (method) — True when the handler is owned by a currently-disabled plugin.
- L67 `register(self, event: str, handler: Callable, priority: int=50, mode: str='sync', plugin: str | None=None)` (method) — Register a handler for an event. Lower priority = runs first.
- L100 `unregister(self, event: str, handler: Callable)` (method) — Remove a handler from an event.
- L104 `fire(self, event: str, **kwargs: Any)` (method) — Fire an event. All registered handlers are called in priority order.
- L142 `_enqueue_async(self, event: str, handler: Callable, kwargs: dict)` (method) — Send a hook-handler invocation to Celery.
- L175 `filter(self, event: str, value: Any, *, raise_errors: bool=False, **kwargs: Any)` (method) — Filter an event — each handler receives the (potentially modified) value
- L215 `_serialize_payload(kwargs: dict[str, Any])` (method)
- L276 `_dispatch_remote(self, event: str, kwargs: dict[str, Any])` (method) — Serialize the event payload and dispatch to (a) any subscribed
- L343 `_deliver_one(self, endpoint, event_name: str, payload: dict)` (method) — One endpoint, one delivery: a delivery owner (webhooks_ui) takes it
- L359 `has_handlers(self, event: str)` (method)
- L362 `list_handlers(self, event: str)` (method)
- L369 `events_of(self, plugin: str)` (method) — Every event a plugin's handlers listen to, sorted (the Help page's
- L378 `clear(self, event: str | None=None)` (method) — Clear handlers. If event is None, clears all.
- L408 `MorpheusEvents` (class) — Catalogue of all built-in hook events.
