---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-09T21:57:01'
updated: '2026-06-09T21:57:01'
---

# plugins/installed/agent_mcp/tests/test_streamable_http.py

Symbols in `plugins/installed/agent_mcp/tests/test_streamable_http.py`.

- L21 `StreamableHttpTransportTests` (class) — The four behaviours that make the endpoint MCP-streamable-compliant.
- L24 `setUp(self)` (method)
- L27 `_post(self, body: dict, accept: str='application/json')` (method)
- L35 `test_get_returns_405(self)` (method) — No server-initiated streams — GET must be Method Not Allowed
- L42 `test_post_json_is_default(self)` (method) — Default Accept (application/json) → JsonResponse, unchanged
- L53 `test_post_sse_wraps_response(self)` (method) — Accept: text/event-stream → response is wrapped in SSE
- L74 `test_initialize_mints_session_id(self)` (method) — initialize → server stamps Mcp-Session-Id so subsequent
- L86 `test_ping_does_not_mint_session_id(self)` (method) — A regular call (no `initialize`) should NOT mint a new
- L94 `test_client_session_id_is_echoed(self)` (method) — If the client sends Mcp-Session-Id, the server must echo it
