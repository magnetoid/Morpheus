---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-09T21:57:01'
updated: '2026-06-09T21:57:01'
---

# plugins/installed/agent_core/models.py

Symbols in `plugins/installed/agent_core/models.py`.

- L22 `AgentRun` (class) — One invocation of an agent.
- L74 `__str__(self)` (method)
- L78 `total_tokens(self)` (method)
- L82 `AgentStep` (class) — One step in a run's trace — mirror of `core.agents.trace.TraceStep`.
- L111 `AgentConversation` (class) — A persistent chat thread between a user (or session) and an agent.
- L136 `AgentMessage` (class) — One message in a conversation thread.
- L161 `AgentMemoryRecord` (class) — DB-backed memory tier (semantic + episodic).
- L187 `BackgroundAgent` (class) — A registered agent that runs autonomously on a schedule.
- L233 `__str__(self)` (method)
- L237 `AgentApprovalRequest` (class) — Pending approval gate for a tool that requires human sign-off.
