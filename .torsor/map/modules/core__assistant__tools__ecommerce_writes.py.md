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

# core/assistant/tools/ecommerce_writes.py

Symbols in `core/assistant/tools/ecommerce_writes.py`.

- L45 `_require_confirmed(confirmed: bool)` (function)
- L50 `_is_staged(context)` (function) — True when the run context asks for staged (propose-only) mode.
- L55 `_obj_ref(obj)` (function) — `'<app_label>.<model>:<pk>'` — the OpsProposal change-object format.
- L60 `_stage(*, context, tool_name: str, kind: str, title: str, summary: str, changes: list[dict], target=None)` (function) — Record an OpsProposal instead of executing (staged-changes design §2).
- L95 `_require_hard_gate(*, hard_gate_ack: str, target_name: str, echo: str)` (function) — Enforce the second-tier confirmation for destructive actions.
- L154 `customers_add_note_tool(*, note: str, id: str='', email: str='', confirmed: bool=False, context: dict | None=None)` (function)
