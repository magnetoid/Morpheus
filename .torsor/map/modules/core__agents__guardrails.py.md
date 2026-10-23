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

# core/agents/guardrails.py

Symbols in `core/agents/guardrails.py`.

- L41 `AIPaused` (class) — The merchant's agent guardrails refuse this call: AI is switched off, or
- L46 `_read(key: str, default)` (function) — Read one agent_core config value, cross-process fresh. Fail-soft.
- L60 `_num(key: str)` (function) — A numeric cap. Blank / unset / bad value / negative → 0.0 (= no cap).
- L71 `agents_paused()` (function) — The global kill switch. Fail-soft to NOT paused — a transient config
- L77 `max_agent_runs_daily()` (function) — Hard ceiling on autonomous agent runs per calendar day. 0 = unlimited.
- L83 `daily_spend_cap_usd()` (function) — Best-effort USD/day ceiling using estimated model pricing. 0 = off.
- L90 `max_price_change_pct()` (function) — Largest single price change (up or down) an agent may make, in percent.
- L96 `max_refund_value()` (function) — Largest single refund an agent may issue, in store currency. 0 = no cap.
- L104 `today_start()` (function) — Start of the current calendar day in the server's active timezone.
- L111 `_runs_today(exclude_id=None)` (function)
- L123 `daily_run_count(exclude_id=None)` (function)
- L127 `daily_spend_usd(exclude_id=None)` (function) — Summed estimated USD across today's runs. Priced per-model (price depends
- L145 `_app_usage_today()` (function) — Model calls apps made today outside agent runs (the dashboard's AI buttons,
- L167 `_assistant_usage_today()` (function) — Linda's token use today, recorded on her replies (her turns are not AgentRuns).
- L184 `run_start_block_reason(exclude_id=None)` (function) — Reason a NEW agent run must be refused at start, or None to allow.
- L203 `model_call_refusal()` (function) — Why a model call must not run now, or '' to allow. The run cap is left
- L221 `run_scope()` (function) — Wrap the agent runtime's OWN provider calls. A model call a tool makes
- L231 `guard_model_call(respond)` (function) — Wrap a provider's ``respond``: refuse when the guardrails say so, and
- L257 `record_model_usage(model: str, prompt_tokens: int, completion_tokens: int)` (function) — Add a call's tokens to today's row for its model. Never raises: losing a
- L292 `_outside_run_usage_today()` (function)
