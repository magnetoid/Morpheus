---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:50'
updated: '2026-10-23T04:51:50'
rules: []
---

# plugins/installed/agent_mcp/scopes.py

Symbols in `plugins/installed/agent_mcp/scopes.py`.

- L203 `token_scopes(entry: Any, surface: str)` (function) — Return the active scope set for a token entry on a given surface.
- L233 `has_scopes(granted: Iterable[str], required: Iterable[str])` (function) — True iff the granted set contains the wildcard, or EVERY required scope.
- L259 `find_entry_for_token(token: str)` (function) — Look up the full entry dict for a presented token. Returns None
