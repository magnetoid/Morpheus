---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-09T21:57:01'
updated: '2026-06-09T21:57:01'
---

# core/assistant/tools/code.py

Symbols in `core/assistant/tools/code.py`.

- L29 `_is_read_only(t)` (function) — A tool is script-safe only if it's READ-ONLY: no declared scope mentions
- L37 `_available_tools(agent)` (function) — The script-callable tools, by name: non-approval AND read-only, drawn from
- L80 `run_python_tool(*, code: str, agent=None, context=None, description: str='')` (function)
- L159 `code_draft_tool(*, name: str, source: str, rationale: str='')` (function)
- L217 `code_list_proposals_tool(*, status: str='')` (function)
- L256 `code_evaluate_proposal_tool(*, proposal_id: str)` (function)
- L313 `code_apply_proposal_tool(*, proposal_id: str, confirmed: bool=False, hard_gate_ack: str='', echo: str='')` (function)
