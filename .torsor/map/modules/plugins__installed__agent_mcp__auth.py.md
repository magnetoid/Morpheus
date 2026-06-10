---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-09T21:57:01'
updated: '2026-06-09T21:57:01'
---

# plugins/installed/agent_mcp/auth.py

Symbols in `plugins/installed/agent_mcp/auth.py`.

- L39 `_present_token(request: HttpRequest)` (function)
- L46 `_service_user()` (function) — Get or lazily create the synthetic Bearer-auth service user.
- L72 `_touch_last_used(token: str)` (function) — Best-effort update of the token's last_used_at timestamp.
- L97 `apply_bearer_user(request: HttpRequest)` (function) — Resolve a Bearer token to a staff service user on `request.user`.
