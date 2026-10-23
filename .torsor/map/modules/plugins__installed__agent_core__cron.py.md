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

# plugins/installed/agent_core/cron.py

Symbols in `plugins/installed/agent_core/cron.py`.

- L41 `Cron` (class)
- L50 `_runs_on(self, day: date)` (method)
- L57 `next_after(self, moment: datetime)` (method) — The first time after ``moment`` the schedule fires, on ``moment``'s clock.
- L77 `_value(token: str, name: str, names: dict)` (function)
- L85 `_field(text: str, name: str, low: int, high: int, names: dict)` (function)
- L108 `parse(expr: str)` (function) — A ``Cron`` from five fields; ``ValueError`` with a readable reason otherwise.
- L127 `shortest_gap(schedule: Cron, after: datetime, runs: int=100)` (function) — The shortest time between two runs among the next ``runs``.
- L140 `schedule_error(expr: str, *, engine: str)` (function) — Why ``expr`` cannot schedule an automation run by ``engine``, or ''.
