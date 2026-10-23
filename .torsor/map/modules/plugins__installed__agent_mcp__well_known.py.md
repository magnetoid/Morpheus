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

# plugins/installed/agent_mcp/well_known.py

Symbols in `plugins/installed/agent_mcp/well_known.py`.

- L42 `_shopping_mcp_endpoint(base: str)` (function) — The MCP server an agent should use for shopping: the checkout cluster
- L53 `ucp_profile(request: HttpRequest)` (function) — GET /.well-known/ucp — the business profile, spec shape (2026-08-25).
- L84 `_trusted_agent_enabled()` (function) — True only when the origin actually honors verified-agent headers — i.e.
- L93 `_capability_live(names)` (function) — True when at least one of the given cluster tool names actually resolves.
- L110 `ucp_manifest(request: HttpRequest)` (function)
- L160 `trusted_agent_manifest(request: HttpRequest)` (function) — Capabilities advertised to Visa TAP / Mastercard Verifiable Intent
