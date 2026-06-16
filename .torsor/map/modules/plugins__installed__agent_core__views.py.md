---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:57'
updated: '2026-06-13T00:49:57'
---

# plugins/installed/agent_core/views.py

Symbols in `plugins/installed/agent_core/views.py`.

- L37 `_decode_body(request)` (function)
- L46 `_check_audience(request, agent_name: str)` (function) — Audience-policy gate. Returns a JsonResponse on denial, else None.
- L66 `_agent_rate_key(request)` (function)
- L75 `invoke_agent_view(request, agent_name: str)` (function)
- L127 `stream_agent_view(request, agent_name: str)` (function) — Server-Sent Events: live trace of a single run.
- L209 `list_agents_view(request)` (function) — Public catalog: which agents are registered, their audience + description.
- L227 `runs_dashboard_view(request)` (function)
- L248 `run_detail_view(request, run_id: str)` (function)
- L264 `merchant_ops_chat_view(request)` (function) — The Merchant Ops chat console (admin only).
- L289 `observability_view(request)` (function) — Aggregate per-agent stats over the last N days.
- L353 `background_agents_view(request)` (function)
- L396 `background_agent_action_view(request, bg_id: str, action: str)` (function)
