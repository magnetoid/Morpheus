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

# plugins/installed/agent_mcp/tests/test_governance.py

Symbols in `plugins/installed/agent_mcp/tests/test_governance.py`.

- L31 `_rpc(method, params=None, _id=1)` (function)
- L35 `McpGovernanceTests` (class)
- L36 `setUp(self)` (method)
- L64 `_call(self, token, name=TOOL, args=None)` (method)
- L72 `_mark_approval_required(self)` (method) — Flip requires_approval on the live registry tool for this test.
- L83 `test_approval_tool_denied_without_grant(self)` (method)
- L93 `test_approval_tool_allowed_with_grant(self)` (method)
- L103 `test_plain_tool_unaffected_by_gate(self)` (method)
- L112 `test_executed_call_writes_agents_decision_row(self)` (method)
- L120 `test_per_token_rate_limit_enforced_and_audited(self)` (method)
- L135 `TrustedAgentAttributionTests` (class) — A verified-agent request that places an order stamps the agent id onto
- L140 `test_order_placed_stamps_agent_from_thread_local(self)` (method)
- L172 `test_plugin_subscribes_order_placed(self)` (method)
- L182 `_name(entry)` (method)
