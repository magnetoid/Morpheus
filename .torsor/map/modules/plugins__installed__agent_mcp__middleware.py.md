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

# plugins/installed/agent_mcp/middleware.py

Symbols in `plugins/installed/agent_mcp/middleware.py`.

- L51 `_origin_verified(request)` (function) — True only when the request carries the Cloudflare-injected shared secret,
- L67 `current_trusted_agent()` (function) — The TrustedAgent for the in-flight request, or None.
- L73 `TrustedAgent` (class)
- L79 `TrustedAgentMiddleware` (class)
- L80 `__init__(self, get_response)` (method)
- L83 `__call__(self, request)` (method)
- L125 `stamp_order_with_agent(order, agent=None)` (function) — Persist the verified agent id onto an order's metadata. Idempotent;
