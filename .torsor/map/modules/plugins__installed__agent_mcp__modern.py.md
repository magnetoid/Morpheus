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

# plugins/installed/agent_mcp/modern.py

Symbols in `plugins/installed/agent_mcp/modern.py`.

- L66 `ModernError` (class) — A validation failure with the JSON-RPC code and HTTP status to send.
- L69 `__init__(self, code: int, message: str, *, status: int=400, data: Any=None)` (method)
- L77 `is_modern(request, body)` (function) — A request is served statelessly when it carries the per-request
- L93 `foreign_origin(request)` (function) — True when a browser-style ``Origin`` names another site: the transport
- L106 `decode_name(value: str)` (function) — ``Mcp-Name`` / ``Mcp-Param-*`` values may carry the Base64 sentinel.
- L118 `validate(request, body)` (function) — Check the modern envelope; return ``{'version', 'method', 'params'}``.
- L133 `_validate_body(body)` (function)
- L153 `_validate_headers(request, method: str, params: dict, version: str)` (function)
- L187 `server_info()` (function)
- L198 `discover_result(*, authed: bool)` (function) — ``server/discover``: versions, capabilities and identity, cacheable.
- L222 `decorate(result: dict, method: str, *, authed: bool)` (function) — Stamp a result with ``resultType``, the server identity and, for the
- L238 `translate_error(code: int)` (function) — Map the legacy-era application codes onto the modern ones.
- L245 `http_status(code: int, *, method_found: bool=True)` (function)
