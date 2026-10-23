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

# plugins/installed/ai_assistant/tests/test_agent_tools.py

Symbols in `plugins/installed/ai_assistant/tests/test_agent_tools.py`.

- L19 `_FakeLLM` (class)
- L22 `__init__(self, raw='{"labels": ["Fiction"]}')` (method)
- L25 `complete(self, prompt, system='', **kw)` (method)
- L28 `embed(self, text)` (method)
- L32 `SemanticSearchToolGatingTests` (class)
- L33 `setUp(self)` (method)
- L36 `_tool_names(self)` (method)
- L39 `test_tool_absent_when_flag_off(self)` (method)
- L43 `test_tool_present_when_flag_on(self)` (method)
- L49 `test_tool_is_callable(self)` (method)
- L61 `ZeroShotToolGatingTests` (class)
- L62 `setUp(self)` (method)
- L65 `_tool_names(self)` (method)
- L68 `test_tool_absent_when_flag_off(self)` (method)
- L72 `test_tool_present_when_flag_on(self)` (method)
- L78 `test_tool_classifies_product_against_categories(self)` (method)
- L104 `test_tool_unknown_slug_is_clean_error(self)` (method)
- L114 `AutonomyGateTests` (class) — ai_assistant answers the scheduler's AUTONOMY_ENABLED filter from the
- L119 `setUp(self)` (method)
- L122 `test_gate_off_by_default(self)` (method)
- L126 `test_gate_on_when_flag_set(self)` (method)
- L130 `test_gate_preserves_upstream_true(self)` (method)
- L135 `ZeroShotServiceTests` (class)
- L136 `test_empty_inputs_short_circuit_without_calling_llm(self)` (method)
- L150 `test_labels_deduped_and_capped(self)` (method)
