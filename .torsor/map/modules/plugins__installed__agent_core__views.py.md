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

# plugins/installed/agent_core/views.py

Symbols in `plugins/installed/agent_core/views.py`.

- L47 `_decode_body(request)` (function)
- L56 `_check_audience(request, agent_name: str)` (function) — Audience-policy gate. Returns a JsonResponse on denial, else None.
- L75 `_agent_rate_key(request)` (function)
- L84 `invoke_agent_view(request, agent_name: str)` (function)
- L136 `stream_agent_view(request, agent_name: str)` (function) — Server-Sent Events: live trace of a single run.
- L218 `list_agents_view(request)` (function) — Public catalog: which agents are registered, their audience + description.
- L237 `runs_dashboard_view(request)` (function)
- L290 `_janus_learning_summary()` (function) — Read-only snapshot of what Janus has learned (the real Janus activity).
- L310 `_janus_activity_log(limit: int=60)` (function) — What the engine has been doing, as one chronological feed.
- L458 `_call_failed(output)` (function) — Both shapes a decision row's ``output`` has carried: the Worker's
- L467 `_call_error(output)` (function)
- L473 `_refusals_since(since)` (function) — Writes the MCP edge turned down in the window (consent, scope, mode) —
- L486 `_describe_tool_call(meta: dict, output, failed: bool)` (function) — A one-line reading of an ``agents.decision`` tool call.
- L510 `_short(value)` (function)
- L515 `_describe_janus_audit(ev)` (function) — A one-line, human reading of a ``janus.*`` audit row.
- L531 `run_detail_view(request, run_id: str)` (function)
- L548 `merchant_ops_chat_view(request)` (function) — The Merchant Ops chat console (admin only).
- L574 `observability_view(request)` (function) — Aggregate per-agent stats over the last N days.
- L684 `background_agents_view(request)` (function)
- L758 `background_agent_action_view(request, bg_id: str, action: str)` (function)
- L787 `memory_list_view(request)` (function)
- L815 `memory_action_view(request)` (function) — POST-only create/edit/delete of LindaMemory rows. Superuser-only — editing
- L869 `reports_list_view(request)` (function)
- L894 `report_action_view(request, report_id)` (function) — POST-only: save the edited text, send the report, dismiss it or reopen it.
