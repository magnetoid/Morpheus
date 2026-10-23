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

# core/agents/tests/test_guardrails.py

Symbols in `core/agents/tests/test_guardrails.py`.

- L23 `_set_guardrail(**kw)` (function) — Persist guardrail config the way the settings panel does.
- L33 `_run(agent_name='w', **kw)` (function)
- L37 `GuardrailConfigTests` (class)
- L38 `test_all_off_by_default(self)` (method)
- L46 `test_agents_paused_reads_config_fresh(self)` (method)
- L55 `test_bad_numeric_config_is_treated_as_no_cap(self)` (method)
- L61 `DailyRunCapTests` (class)
- L62 `test_run_cap_blocks_a_new_run(self)` (method)
- L68 `test_run_cap_excludes_the_current_run(self)` (method)
- L77 `DailySpendCapTests` (class)
- L78 `test_spend_cap_blocks_a_priced_model(self)` (method)
- L84 `test_spend_cap_blocks_the_production_model(self)` (method)
- L92 `test_spend_cap_is_still_a_noop_for_a_genuinely_unpriced_model(self)` (method)
- L100 `KillSwitchRuntimeTests` (class)
- L101 `test_paused_aborts_before_any_provider_call(self)` (method)
- L110 `test_run_cap_aborts_before_any_provider_call(self)` (method)
- L120 `test_runs_normally_with_guardrails_off(self)` (method)
- L128 `KillSwitchLindaTests` (class)
- L129 `test_linda_declines_gracefully_when_paused(self)` (method)
