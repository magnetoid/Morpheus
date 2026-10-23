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

# plugins/installed/agent_mcp/dashboard.py

Symbols in `plugins/installed/agent_mcp/dashboard.py`.

- L49 `_approval_tools()` (function) — Every protected tool a token can be granted: the admin server's own tools
- L67 `_approval_tool_names()` (function)
- L71 `_load_entries()` (function) — Return the stored entries, PRESERVING every stored key.
- L111 `_save_entries(entries: list[dict])` (function)
- L121 `_mask(token: str)` (function)
- L129 `_new_token()` (function) — Generate a 32-byte urlsafe token with a recognisable prefix.
- L134 `_find_entry(entries: list[dict], token_id: str)` (function)
- L141 `_scope_list_from_form(post, prefix: str)` (function) — Read checked scope names matching `{prefix}_<scope>` from a
- L180 `preset_scopes(preset: str)` (function)
- L200 `_surface_scopes(post, prefix: str)` (function) — The scopes a permissions form sets on one surface. "Talk to Janus" is kept
- L211 `_audit(request, event_type: str, entry: dict, **extra)` (function) — One audit row per token change. Never the secret.
- L226 `_kit(request, entry: dict, *, secret: str='')` (function)
- L238 `_now()` (function)
- L242 `_create(request)` (function)
- L273 `_rotate(request)` (function)
- L289 `_revoke(request)` (function)
- L308 `_save_scopes(request)` (function)
- L336 `_row(entry)` (function)
- L358 `_readable_time(value)` (function) — ``2026-10-10T21:45:18Z`` as ``2026-10-10 21:45 UTC``; anything else as stored.
- L366 `_edit_context(entry)` (function)
- L386 `tokens_view(request)` (function) — Create, connect, rotate, set permissions on and revoke API tokens.
- L446 `_scope_summary(scopes: list[str] | None)` (function) — Human-friendly label for a scope set, used in the table column.
