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

# core/assistant/tools/spawn.py

Symbols in `core/assistant/tools/spawn.py`.

- L42 `_execute_worker_run(*, run_id: str, objective: str, context: dict[str, Any], skills: tuple[str, ...]=())` (function) — Run the Worker agent for a pre-created AgentRun row.
- L211 `spawn_workers_tool(*, jobs: list[dict[str, Any]])` (function)
- L297 `poll_workers_tool(*, run_ids: list[str])` (function)
- L362 `wait_for_workers_tool(*, run_ids: list[str], timeout_s: float=120.0)` (function)
