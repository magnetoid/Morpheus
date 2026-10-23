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

# core/agents/tests/test_staged_gate.py

Symbols in `core/agents/tests/test_staged_gate.py`.

- L24 `_single_dispatch_provider()` (function) — One tool call to `do_thing`, then a final answer — a single dispatch.
- L34 `_staging_tool(*, handler)` (function) — A requires_approval tool that ALSO implements staging (the _tool helper
- L46 `StagedApprovalGateScopeTests` (class)
- L47 `_run(self, tool, *, context=None)` (method)
- L53 `test_non_staging_tool_still_gated_under_staged_context(self)` (method)
- L69 `test_staging_tool_exempt_under_staged_context(self)` (method)
- L80 `test_staging_tool_still_gated_without_staged_context(self)` (method)
