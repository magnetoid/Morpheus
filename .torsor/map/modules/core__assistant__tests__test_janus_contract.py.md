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

# core/assistant/tests/test_janus_contract.py

Symbols in `core/assistant/tests/test_janus_contract.py`.

- L44 `_config_keys(text: str)` (function) — Dotted keys of the generated YAML: the MCP server name as ``*``, a hook as its event.
- L71 `ContractInStepTests` (class)
- L72 `test_every_toolset_a_turn_can_load_is_in_the_contract(self)` (method)
- L76 `test_every_config_key_morpheus_writes_is_proved_or_waived(self)` (method)
- L92 `test_the_env_vars_a_turn_sets_are_in_the_contract(self)` (method)
- L99 `test_every_chat_option_a_turn_passes_is_in_the_contract(self)` (method)
- L124 `test_the_notices_stripped_from_answers_are_watched(self)` (method)
- L130 `_fake_janus(root: Path, *, search_tools=('web_search',), drop: str='')` (function) — A minimal Janus tree with just what the contract reads.
- L210 `ContractScriptTests` (class) — The script itself, run the way the build and the updater run it.
- L213 `_run(self, **fake)` (method)
- L231 `_failing(report)` (method)
- L234 `test_a_compatible_janus_passes(self)` (method)
- L239 `test_a_toolset_that_grows_a_tool_fails(self)` (method)
- L244 `test_a_config_key_nothing_reads_any_more_fails(self)` (method)
- L248 `test_a_renamed_system_prompt_variable_fails(self)` (method)
- L252 `test_it_imports_nothing_from_morpheus(self)` (method)
