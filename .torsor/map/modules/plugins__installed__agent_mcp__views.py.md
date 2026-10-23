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

# plugins/installed/agent_mcp/views.py

Symbols in `plugins/installed/agent_mcp/views.py`.

- L80 `_public_tools()` (function) — Resolve the curated tool whitelist into actual tool objects.
- L126 `_api_keys()` (function) — Active API keys from PluginConfig['agent_mcp']['public_keys'].
- L155 `_is_authed(request: HttpRequest)` (function)
- L173 `_handle_initialize(params: dict, authed: bool)` (function)
- L195 `_handle_tools_list(params: dict, authed: bool)` (function)
- L229 `_mcp_actor()` (function) — Audit identity for the in-flight call: token label or staff session.
- L237 `_audit_denied(tool_name: str, reason: str)` (function) — Denials are audit events too — refusals were previously unrecorded.
- L254 `_audit_call(tool_name: str, args: dict, output: Any=None, error: str='', t0=None)` (function) — One agents.decision row per executed MCP tool call (EU AI Act art. 12).
- L289 `_enforce_rate_limit(tool_name: str)` (function) — Per-token fixed-window limit on tool execution. Cache-outage = fail-open
- L325 `_validate_one_arg(name: str, val, spec: dict)` (function) — Validate a single argument against its property spec. '' when valid.
- L350 `_validate_tool_args(tool, args: dict)` (function) — Validate `args` against `tool.schema` (a JSON-Schema subset). Returns an
- L378 `_enforce_discovery_rate_limit(method: str)` (function) — Rate-limit the UNAUTHENTICATED discovery methods (initialize / tools/list
- L405 `_exposed_tool(name: str, turn)` (function) — Resolve a tool the active cluster exposes, or Linda's catalogue for a turn.
- L419 `_call_for_turn(tool, name: str, args: dict, turn)` (function) — A Linda turn: Linda's scope profile, the mode, and HUMAN consent from the
- L431 `_handle_tools_call(params: dict, authed: bool)` (function)
- L563 `_handle_resources_list(params: dict, authed: bool)` (function) — Surface a small set of useful entry-point resources.
- L609 `_handle_resources_read(params: dict, authed: bool)` (function)
- L677 `_RpcError` (class)
- L678 `__init__(self, code: int, message: str, data: Any=None)` (method)
- L693 `_active_token_scopes()` (function) — Token scopes for the in-flight request — populated by
- L702 `_stash_linda_turn(request: HttpRequest)` (function) — Carry a verified Linda turn into the handlers; attribute its audit rows.
- L719 `rpc_endpoint(request: HttpRequest)` (function) — Single JSON-RPC 2.0 entry point.
- L807 `_serve_modern(request: HttpRequest, body: Any, authed: bool)` (function) — One stateless 2026-07-28 request: validate the mirrored headers, run
- L817 `_modern_payload(request: HttpRequest, body: Any, msg_id: Any, authed: bool)` (function)
- L849 `_dispatch(message: dict, authed: bool)` (function)
- L875 `_error_envelope(msg_id: Any, code: int, message: str, data: Any=None)` (function)
- L886 `health(request: HttpRequest)` (function) — Liveness probe — useful for AI clients that want to verify the
- L900 `manifest(request: HttpRequest)` (function) — ChatGPT-style plugin manifest. Mounted at /mcp/v1/manifest.json so
