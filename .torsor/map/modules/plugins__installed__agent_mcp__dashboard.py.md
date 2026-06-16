---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:57'
updated: '2026-06-13T00:49:57'
---

# plugins/installed/agent_mcp/dashboard.py

Symbols in `plugins/installed/agent_mcp/dashboard.py`.

- L45 `_load_entries()` (function) — Return the stored entries, normalised to dict shape.
- L77 `_save_entries(entries: list[dict])` (function)
- L87 `_mask(token: str)` (function)
- L95 `_new_token()` (function) — Generate a 32-byte urlsafe token with a recognisable prefix.
- L100 `_find_entry(entries: list[dict], token_id: str)` (function)
- L107 `_scope_list_from_form(post, prefix: str)` (function) — Read checked scope names matching `{prefix}_<scope>` from a
- L122 `tokens_view(request)` (function) — List + create + revoke MCP admin tokens.
- L257 `_scope_summary(scopes: list[str] | None)` (function) — Human-friendly label for a scope set, used in the table column.
