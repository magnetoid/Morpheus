---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:56'
updated: '2026-06-13T00:49:56'
---

# api/schema.py

Symbols in `api/schema.py`.

- L24 `CoreQuery` (class)
- L26 `ping(self)` (method)
- L30 `version(self)` (method)
- L34 `active_plugins(self)` (method)
- L41 `CoreMutation` (class)
- L43 `ping(self)` (method)
- L47 `_PermissionToGraphQLError` (class) — Map our PermissionDenied to a structured GraphQL error response.
- L50 `on_executing_end(self)` (method)
- L63 `_MaskUnhandledErrors` (class) — Mask any unhandled exception inside a resolver to `INTERNAL_ERROR` and
- L73 `on_executing_end(self)` (method)
- L112 `build_schema()` (function) — Assemble the schema from core types + all plugin extension modules.
- L153 `get_schema()` (function)
- L162 `warm_schema()` (function) — Pre-build the schema to remove first-request latency.
