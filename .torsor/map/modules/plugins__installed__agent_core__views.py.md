---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-09T21:57:01'
updated: '2026-06-09T21:57:01'
---

# plugins/installed/agent_core/views.py

Symbols in `plugins/installed/agent_core/views.py`.

- L32 `_decode_body(request)` (function)
- L41 `_check_audience(request, agent_name: str)` (function) — Audience-policy gate. Returns a JsonResponse on denial, else None.
- L61 `_agent_rate_key(request)` (function)
- L70 `invoke_agent_view(request, agent_name: str)` (function)
- L119 `stream_agent_view(request, agent_name: str)` (function) — Server-Sent Events: live trace of a single run.
- L197 `list_agents_view(request)` (function) — Public catalog: which agents are registered, their audience + description.
- L213 `runs_dashboard_view(request)` (function)
- L230 `run_detail_view(request, run_id: str)` (function)
- L242 `merchant_ops_chat_view(request)` (function) — The Merchant Ops chat console (admin only).
- L262 `observability_view(request)` (function) — Aggregate per-agent stats over the last N days.
- L318 `background_agents_view(request)` (function)
- L354 `background_agent_action_view(request, bg_id: str, action: str)` (function)
