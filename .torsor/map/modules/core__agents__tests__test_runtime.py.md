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

# core/agents/tests/test_runtime.py

Symbols in `core/agents/tests/test_runtime.py`.

- L18 `_agent(*, scopes=None, tools=(), max_steps=8, requires_approval=False)` (function) — A bare MorpheusAgent instance (NOT a subclass — the pre-commit hook
- L32 `_tool(name='do_thing', *, scopes=None, requires_approval=False, handler=None)` (function)
- L42 `_AlwaysToolProvider` (class)
- L45 `respond(self, **_kw)` (method)
- L49 `_BoomProvider` (class)
- L52 `respond(self, **_kw)` (method)
- L56 `AgentRuntimeTests` (class)
- L57 `_run(self, agent, provider, **kw)` (method)
- L62 `test_final_answer_no_tools(self)` (method)
- L72 `test_tool_dispatch_then_final(self)` (method)
- L94 `test_dotted_tool_name_is_api_safe_and_resolves_both_spellings(self)` (method)
- L122 `test_unknown_tool_recovers(self)` (method)
- L135 `test_malformed_args_surface_as_tool_error(self)` (method) — A tool call the provider couldn't parse (parse_error set) is fed back
- L162 `test_scope_denied_feeds_error_not_crash(self)` (method)
- L175 `test_tool_error_recovers(self)` (method)
- L189 `test_approval_rejected_skips_tool(self)` (method)
- L204 `test_approval_granted_runs_tool(self)` (method)
- L217 `test_approval_fail_closed_without_check(self)` (method)
- L236 `test_approval_gate_exempt_in_staged_mode(self)` (method)
- L264 `test_provider_failure_aborts(self)` (method)
- L269 `test_max_steps_exceeded(self)` (method)
- L275 `test_token_budget_exceeded_aborts(self)` (method)
- L293 `test_zero_budget_is_unlimited(self)` (method)
- L299 `test_returns_tool_result_object(self)` (method)
- L312 `test_degraded_sentinel_is_a_failure_not_a_final_answer(self)` (method)
