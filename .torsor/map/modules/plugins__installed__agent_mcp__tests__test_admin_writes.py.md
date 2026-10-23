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

# plugins/installed/agent_mcp/tests/test_admin_writes.py

Symbols in `plugins/installed/agent_mcp/tests/test_admin_writes.py`.

- L26 `_rpc(method, params=None, _id=1)` (function)
- L30 `AdminWritePathTests` (class)
- L31 `setUp(self)` (method)
- L57 `_call(self, endpoint, token, name, args=None)` (method)
- L65 `_tool(self)` (method)
- L75 `test_write_tool_is_reachable_on_admin_endpoint(self)` (method) — The old pre-check returned 'tool not exposed' (-32601) here — the
- L84 `test_ungranted_token_denied_when_tool_requires_approval(self)` (method)
- L94 `test_write_tool_still_hidden_on_legacy_public_endpoint(self)` (method)
- L98 `test_scopeless_token_cannot_write_on_admin(self)` (method)
