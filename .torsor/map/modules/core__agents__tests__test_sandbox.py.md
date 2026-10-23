---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:49'
updated: '2026-10-23T04:51:49'
rules: []
---

# core/agents/tests/test_sandbox.py

Symbols in `core/agents/tests/test_sandbox.py`.

- L14 `SandboxTests` (class)
- L15 `test_returns_result_variable(self)` (method)
- L18 `test_blocks_import(self)` (method)
- L22 `test_blocks_dunder_access(self)` (method)
- L26 `test_blocks_open_and_eval_names(self)` (method)
- L32 `test_timeout(self)` (method)
- L45 `test_in_script_error_is_wrapped(self)` (method)
- L49 `test_extra_globals_bridge(self)` (method)
- L54 `_tool(name, *, requires_approval=False, scopes=None, output='ok')` (function)
- L65 `_StubAgent` (class)
- L66 `__init__(self, tools, scopes=None)` (method)
- L70 `get_tools(self)` (method)
- L74 `RunPythonBridgeTests` (class)
- L75 `_run(self, code, tools, agent_scopes=None)` (method)
- L78 `test_call_invokes_read_tool(self)` (method)
- L83 `test_approval_gated_tool_not_callable(self)` (method)
- L90 `test_unknown_tool_rejected(self)` (method)
- L94 `test_write_scoped_tool_not_callable(self)` (method)
- L102 `test_scope_enforced_in_bridge(self)` (method)
- L112 `test_call_cap_enforced(self)` (method)
- L117 `test_composes_multiple_calls(self)` (method)
