---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:57'
updated: '2026-06-13T00:49:57'
---

# plugins/installed/agent_core/models.py

Symbols in `plugins/installed/agent_core/models.py`.

- L24 `AgentRun` (class) — One invocation of an agent.
- L78 `__str__(self)` (method)
- L82 `total_tokens(self)` (method)
- L86 `AgentStep` (class) — One step in a run's trace — mirror of `core.agents.trace.TraceStep`.
- L115 `AgentConversation` (class) — A persistent chat thread between a user (or session) and an agent.
- L142 `AgentMessage` (class) — One message in a conversation thread.
- L173 `AgentMemoryRecord` (class) — DB-backed memory tier (semantic + episodic).
- L199 `BackgroundAgent` (class) — A registered agent that runs autonomously on a schedule.
- L252 `__str__(self)` (method)
- L256 `AgentApprovalRequest` (class) — Pending approval gate for a tool that requires human sign-off.
