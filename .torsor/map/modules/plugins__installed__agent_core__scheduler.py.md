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

# plugins/installed/agent_core/scheduler.py

Symbols in `plugins/installed/agent_core/scheduler.py`.

- L35 `min_interval_s(engine: str)` (function)
- L39 `_running_key(bg)` (function)
- L43 `mark_running(bg)` (function) — Take the run lock. False when a run is already in flight.
- L50 `is_running(bg)` (function)
- L56 `clear_running(bg)` (function)
- L62 `_store_timezone()` (function) — The merchant's time zone (Settings → General), else the project's.
- L76 `next_daily(at, now=None)` (function) — The next time the store's clock reads `at` (a `datetime.time`).
- L83 `next_cron(expr: str, now=None)` (function) — The next time the store's clock matches the cron schedule `expr`.
- L90 `first_run_at(bg)` (function) — When a new or resumed automation runs first: its next slot when it has a
- L100 `schedule_next(bg)` (function)
- L109 `scheduled_runs_on()` (function) — Whether the tick runs automations on their schedule (Settings → AI →
- L121 `create_automation(*, name: str, prompt: str, owner, engine: str='linda', agent_name: str='worker', interval_seconds: int=3600, daily_at=None, cron: str='')` (function) — A new automation, scheduled. ``ValueError`` says what is wrong with the input.
- L159 `pause(bg)` (function)
- L164 `resume(bg)` (function) — Active again with its failures forgotten, from its next slot.
- L172 `fire(bg)` (function) — Run one BackgroundAgent now. Returns a small status dict.
- L239 `tick()` (function) — Run every active BackgroundAgent whose next_run_at <= now.
