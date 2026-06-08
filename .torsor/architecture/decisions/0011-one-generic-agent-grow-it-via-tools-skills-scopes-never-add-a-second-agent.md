---
type: decision
status: accepted
tags:
- adr
links: []
created: '2026-06-07T15:28:11'
updated: '2026-06-07T15:28:11'
rules:
- id: no-second-agent-framework
  pattern: langchain|crewai|autogen|autogpt|llama_index|AgentExecutor|class\s+\w*Agent\b
  message: Do not add a second agent framework/orchestrator or a specialist Agent
    class. Extend the single Worker via @tool + scopes (Skill bundle), or wrap an
    SDK as one tool.
- id: agent-grows-by-tools
  pattern: '@tool\('
  message: 'Good: plugins extend the agent by contributing tools + scopes. Keep tools
    plugin-owned; don''t fork the agent.'
---

# ADR 0011: One generic agent — grow it via tools/skills/scopes; never add a second agent

## Context
Strategic question: as AI capability grows, do we adopt another agent framework (LangChain/CrewAI/AutoGPT/etc.) or grow the existing native Worker? Morpheus already has a coherent agent layer in core (agent_core, agent_mcp, ai_assistant/Linda, the Worker, the @tool registry, scopes, hard-gates, hooks). Adding a second orchestrator would create a second tool registry, permission model, and memory store — duplication at the brain, worse than UI duplication.

## Decision
There is exactly ONE generic agent (the Worker / Linda). It gets smarter the same way the dashboard does — by CONTRIBUTION: a plugin extends the agent by registering @tool functions + scopes, never by adding a new agent class or framework. Specialization = a Skill bundle + caller scopes + tools, not a specialist Agent subclass. A second agent system is only ever justified as (a) a swappable LLM BACKEND behind the Worker (already abstracted), or (b) a specialized SDK wrapped as a single tool the Worker calls — never as a parallel orchestrator. Reaffirms the existing rule: Morpheus has ONE Worker.

## Consequences
One coherent brain that fully knows the shop; capabilities grow without touching agent code. No competing registries/permission models. Plugins teach the agent by shipping tools, mirroring how they ship DashboardPages/StorefrontBlocks/settings panels — one mental model.
