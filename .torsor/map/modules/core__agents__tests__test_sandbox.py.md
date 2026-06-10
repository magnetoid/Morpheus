---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-10T20:08:48'
updated: '2026-06-10T20:08:48'
---

# core/agents/tests/test_sandbox.py

Symbols in `core/agents/tests/test_sandbox.py`.

- L12 `SandboxTests` (class)
- L13 `test_returns_result_variable(self)` (method)
- L16 `test_blocks_import(self)` (method)
- L20 `test_blocks_dunder_access(self)` (method)
- L24 `test_blocks_open_and_eval_names(self)` (method)
- L30 `test_timeout(self)` (method)
- L34 `test_in_script_error_is_wrapped(self)` (method)
- L38 `test_extra_globals_bridge(self)` (method)
- L43 `_tool(name, *, requires_approval=False, scopes=None, output='ok')` (function)
- L54 `_StubAgent` (class)
- L55 `__init__(self, tools, scopes=None)` (method)
- L59 `get_tools(self)` (method)
- L63 `RunPythonBridgeTests` (class)
- L64 `_run(self, code, tools, agent_scopes=None)` (method)
- L67 `test_call_invokes_read_tool(self)` (method)
- L72 `test_approval_gated_tool_not_callable(self)` (method)
- L79 `test_unknown_tool_rejected(self)` (method)
- L83 `test_write_scoped_tool_not_callable(self)` (method)
- L91 `test_scope_enforced_in_bridge(self)` (method)
- L101 `test_call_cap_enforced(self)` (method)
- L106 `test_composes_multiple_calls(self)` (method)
