---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:57'
updated: '2026-06-13T00:49:57'
---

# plugins/installed/agent_mcp/auth.py

Symbols in `plugins/installed/agent_mcp/auth.py`.

- L40 `_present_token(request: HttpRequest)` (function)
- L47 `_service_user()` (function) — Get or lazily create the synthetic Bearer-auth service user.
- L77 `_touch_last_used(token: str)` (function) — Best-effort update of the token's last_used_at timestamp.
- L103 `apply_bearer_user(request: HttpRequest)` (function) — Resolve a Bearer token to a staff service user on `request.user`.
