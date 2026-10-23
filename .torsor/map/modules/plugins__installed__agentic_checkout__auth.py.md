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

# plugins/installed/agentic_checkout/auth.py

Symbols in `plugins/installed/agentic_checkout/auth.py`.

- L29 `_acp_granted(entry)` (function) — ACP scope set for a token entry — explicit opt-in, NO wildcard.
- L45 `_bearer_token(request: HttpRequest)` (function)
- L52 `require_acp_scope(request: HttpRequest, scope: str=ACP_SCOPE)` (function) — Gate an ACP request. Returns ``None`` when authorised, else a 401/403.
