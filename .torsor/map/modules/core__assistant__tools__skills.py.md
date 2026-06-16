---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:57'
updated: '2026-06-13T00:49:57'
---

# core/assistant/tools/skills.py

Symbols in `core/assistant/tools/skills.py`.

- L24 `all_resolvable_tools()` (function) — Every tool resolvable by name = Linda's default catalog ∪ plugin-registered
- L45 `load_learned_skills()` (function) — Register every enabled LearnedSkill into the skill_registry. Called at boot
- L101 `skills_distill_tool(*, name: str, label: str, tool_names: list, description: str='', system_prompt_prelude: str='', examples: list | None=None)` (function)
- L159 `record_skill_outcome(name: str, success: bool)` (function) — Record one use outcome on a LearnedSkill. Auto-retires (disables +
- L231 `skills_record_outcome_tool(*, name: str, success: bool, note: str='')` (function)
- L269 `skills_list_tool(*, include_disabled: bool=False)` (function)
