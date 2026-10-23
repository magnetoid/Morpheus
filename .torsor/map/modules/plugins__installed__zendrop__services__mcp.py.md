---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:52'
updated: '2026-10-23T04:51:52'
rules: []
---

# plugins/installed/zendrop/services/mcp.py

Symbols in `plugins/installed/zendrop/services/mcp.py`.

- L41 `_classify(name: str)` (function)
- L55 `McpError` (class) — Zendrop could not be reached or refused the call (message is token-free).
- L59 `access_token()` (function)
- L67 `_post(payload: dict, token: str, session_id: str | None=None)` (function)
- L82 `_parse(resp)` (function) — The JSON-RPC envelope from a JSON body or an SSE stream (``data:`` lines).
- L98 `rpc(method: str, params: dict | None=None, *, token: str, session_id: str | None=None)` (function) — One JSON-RPC call. Returns ``(result, session_id)``.
- L116 `list_tools(token: str)` (function) — ``initialize`` + ``tools/list``: the server's identity and its tool catalogue.
- L141 `capabilities(tools: list[dict])` (function) — Group tool names by what they let a merchant do (heuristic, see _classify).
- L152 `test_connection()` (function) — Connect with the stored token; cache and return a snapshot for the page.
- L175 `cached_connection()` (function)
