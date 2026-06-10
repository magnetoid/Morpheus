---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-09T21:57:01'
updated: '2026-06-09T21:57:01'
---

# plugins/installed/agent_mcp/views.py

Symbols in `plugins/installed/agent_mcp/views.py`.

- L65 `_public_tools()` (function) — Resolve the curated tool whitelist into actual tool objects.
- L94 `_api_keys()` (function) — Active API keys from PluginConfig['agent_mcp']['public_keys'].
- L122 `_is_authed(request: HttpRequest)` (function)
- L133 `_handle_initialize(params: dict, authed: bool)` (function)
- L155 `_handle_tools_list(params: dict, authed: bool)` (function)
- L173 `_handle_tools_call(params: dict, authed: bool)` (function)
- L237 `_handle_resources_list(params: dict, authed: bool)` (function) — Surface a small set of useful entry-point resources.
- L270 `_handle_resources_read(params: dict, authed: bool)` (function)
- L319 `_RpcError` (class)
- L320 `__init__(self, code: int, message: str, data: Any=None)` (method)
- L334 `_active_token_scopes()` (function) — Token scopes for the in-flight request — populated by
- L344 `rpc_endpoint(request: HttpRequest)` (function) — Single JSON-RPC 2.0 entry point.
- L402 `_dispatch(message: dict, authed: bool)` (function)
- L424 `_error_envelope(msg_id: Any, code: int, message: str, data: Any=None)` (function)
- L435 `health(request: HttpRequest)` (function) — Liveness probe — useful for AI clients that want to verify the
- L447 `manifest(request: HttpRequest)` (function) — ChatGPT-style plugin manifest. Mounted at /mcp/v1/manifest.json so
