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

# plugins/installed/agent_core/tasks.py

Symbols in `plugins/installed/agent_core/tasks.py`.

- L11 `background_agents_tick(self)` (function) — Run every active BackgroundAgent whose next_run_at <= now.
- L22 `run_linda_automation(self, automation_id: str)` (function) — One Linda automation run (a Janus turn, up to the turn limit plus margin).
- L33 `sweep_stuck_runs(self, older_than_minutes: int=15)` (function) — Fail AgentRuns wedged in a non-terminal state after their worker died.
- L64 `generate_daily_digest(self)` (function) — Nightly merchant digest — posted as a MerchantInsight 'report'.
