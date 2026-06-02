---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-02T18:07:51'
updated: '2026-06-02T18:07:51'
---

# api/schema.py

Symbols in `api/schema.py`.

- L24 `CoreQuery` (class)
- L26 `ping(self)` (method)
- L30 `version(self)` (method)
- L34 `active_plugins(self)` (method)
- L40 `CoreMutation` (class)
- L42 `ping(self)` (method)
- L46 `_PermissionToGraphQLError` (class) — Map our PermissionDenied to a structured GraphQL error response.
- L49 `on_executing_end(self)` (method)
- L62 `_MaskUnhandledErrors` (class) — Mask any unhandled exception inside a resolver to `INTERNAL_ERROR` and
- L72 `on_executing_end(self)` (method)
- L108 `build_schema()` (function) — Assemble the schema from core types + all plugin extension modules.
- L149 `get_schema()` (function)
- L158 `warm_schema()` (function) — Pre-build the schema to remove first-request latency.
