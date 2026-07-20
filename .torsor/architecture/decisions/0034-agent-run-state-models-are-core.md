# 34. Agent run-state models are core

Date: 2026-07-20

## Status

Accepted. Completes the core→plugin boundary refactor
(`docs/plans/architecture-debt-refactor-2026-07.md`, Phase 4); builds on
ADR 0029 (Linda + the agent layer are permanent core) and ADR 0017 (the
kernel is a clean set of extension points).

## Context

`AgentRun`, `AgentStep`, and `AgentApprovalRequest` — the persistence of
every agent invocation, its audit-grade step trace, and the human-approval
gate — lived in the `agent_core` plugin, while the runtime that creates and
writes them is permanently core (ADR 0029): `core/agents/runtime.py` drives
runs, `core/assistant/tools/spawn.py` creates/persists them for delegated
Workers. That forced the last `core → plugins.installed.*` import in the
boundary ratchet (`spawn.py → agent_core.models`) and meant kernel
orchestration state was owned by a togglable plugin.

`contribute_agent_tools()` was the wrong mechanism (this is kernel
orchestration, not a domain-data tool body), and a service-facade would
have added an indirection layer for transactional row lifecycle without
resolving the ownership question.

## Decision

The run-state models move INTO core: `core/agents/models.py`, registered
under the `core` app (imported from `core/models.py`). The state a
permanently-core runtime persists is core state.

- **DB tables are unchanged** — explicit `db_table` pins the original
  `agent_core_agentrun` / `agent_core_agentstep` /
  `agent_core_agentapprovalrequest` names, and the index names are
  byte-identical (derived from db_table). The move is
  `SeparateDatabaseAndState` on both sides (`core.0021`,
  `assistant.0013`, `agent_core.0004`) — **zero SQL**, verified via
  `sqlmigrate` (all three print `(no-op)`), so no 503 window and no
  cross-type FK retargets (the CLAUDE.md sqlite-hides-Postgres landmine).
- **agent_core keeps its product surface** — `AgentConversation`,
  `AgentMessage`, `AgentMemoryRecord`, `BackgroundAgent` stay in the
  plugin; its `models.py` re-exports the moved classes so every existing
  `plugins.installed.agent_core.models` import (views, GraphQL, tasks,
  scheduler, admin_dashboard) keeps working — plugin→core is the allowed
  direction.
- `assistant.OpsProposal.agent_run` and `agent_core.AgentMessage.run`
  FK string refs retarget to `'core.AgentRun'` (same table, same UUID PK
  — state-only `AlterField`).

## Consequences

- The core-boundary ratchet reaches **0**: `core/` imports nothing from
  `plugins.installed.*`; the baseline allowlist is empty and can only
  stay empty (new leaks fail CI + the PostToolUse hook).
- Disabling `agent_core` no longer even nominally implicates kernel
  run-state; the plugin remains the dashboard/GraphQL/scheduler surface
  over that state.
- A fresh database builds correctly in either order: `agent_core`'s
  history CREATEs the tables; `core.0021` (which depends on
  `agent_core.0003`) maps state onto them with no SQL.
