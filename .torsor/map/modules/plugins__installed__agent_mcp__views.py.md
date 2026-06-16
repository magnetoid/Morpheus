---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:57'
updated: '2026-06-13T00:49:57'
---

# plugins/installed/agent_mcp/views.py

Symbols in `plugins/installed/agent_mcp/views.py`.

- L72 `_public_tools()` (function) — Resolve the curated tool whitelist into actual tool objects.
- L102 `_api_keys()` (function) — Active API keys from PluginConfig['agent_mcp']['public_keys'].
- L131 `_is_authed(request: HttpRequest)` (function)
- L142 `_handle_initialize(params: dict, authed: bool)` (function)
- L164 `_handle_tools_list(params: dict, authed: bool)` (function)
- L182 `_handle_tools_call(params: dict, authed: bool)` (function)
- L249 `_handle_resources_list(params: dict, authed: bool)` (function) — Surface a small set of useful entry-point resources.
- L282 `_handle_resources_read(params: dict, authed: bool)` (function)
- L332 `_RpcError` (class)
- L333 `__init__(self, code: int, message: str, data: Any=None)` (method)
- L348 `_active_token_scopes()` (function) — Token scopes for the in-flight request — populated by
- L359 `rpc_endpoint(request: HttpRequest)` (function) — Single JSON-RPC 2.0 entry point.
- L416 `_dispatch(message: dict, authed: bool)` (function)
- L438 `_error_envelope(msg_id: Any, code: int, message: str, data: Any=None)` (function)
- L449 `health(request: HttpRequest)` (function) — Liveness probe — useful for AI clients that want to verify the
- L463 `manifest(request: HttpRequest)` (function) — ChatGPT-style plugin manifest. Mounted at /mcp/v1/manifest.json so
