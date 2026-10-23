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

# plugins/installed/zendrop/tests/test_mcp.py

Symbols in `plugins/installed/zendrop/tests/test_mcp.py`.

- L14 `_Resp` (class)
- L15 `__init__(self, status=200, body=None, headers=None, text='')` (method)
- L21 `json(self)` (method)
- L27 `_server(tools)` (function) — A fake Zendrop MCP server answering initialize / tools/list over JSON and SSE.
- L61 `json_dumps(obj)` (function)
- L65 `McpClientTests` (class)
- L66 `setUp(self)` (method)
- L73 `test_list_tools_speaks_json_rpc_and_reads_an_sse_reply(self)` (method)
- L92 `test_a_rejected_token_is_a_clear_error_without_the_token_in_it(self)` (method)
- L105 `test_a_json_rpc_error_is_surfaced(self)` (method)
- L114 `test_connection_test_without_a_token_says_so_and_caches_nothing(self)` (method)
- L120 `test_connection_test_caches_the_snapshot(self)` (method)
- L128 `test_network_failure_is_reported_without_raising_through_the_page(self)` (method)
