---
type: decision
status: accepted
tags:
- adr
links: []
created: '2026-07-05T23:29:03'
updated: '2026-07-05T23:29:03'
rules:
- id: linda-agent-layer-stays-core
  statement: "Linda and the agent orchestration layer must stay in Morpheus core \u2014\
    \ never plugin-ize them."
  applies_to: core/agents/**, core/assistant/** (runtime + dispatch), core/safety.py,
    scopes
  guard: No plugin may own or relocate Linda, the single Worker, the LLM providers,
    the agent runtime, the tool dispatch/registry, the scopes system, or the core/safety.py
    boundary. Only plugin-data tool BODIES may migrate out of core/assistant/tools/*
    into their owning plugin via contribute_agent_tools(); the collection point and
    runtime remain in core.
  severity: error
---

# ADR 0029: Linda and the agent layer are permanent core — never a plugin

## Context
The architecture-debt refactor reduces core→plugin coupling by moving the tool bodies in core/assistant/tools/* (which read specific plugins' models) out into their owning plugins via contribute_agent_tools(). That decoupling must never be misread as "make the assistant/Linda a plugin." Per ADR 0017 core stays a clean set of extension points, but the agent orchestration layer is itself one of the foundational core subsystems (alongside auth, hooks, i18n kernel, request_id, observability, the self-improvement loop, and the core/safety.py boundary). Linda is the brain of the AI-first surface and must be always-on, not togglable. The user re-stated this explicitly while reviewing the refactor.

## Decision
Linda (the orchestrator), the single generic Worker, the LLM providers, the agent runtime, the tool dispatch/registry, the scopes system, and core/safety.py remain in core permanently and must never be refactored into a plugin. When reducing core→plugin coupling, ONLY the tool implementations that read/write a specific plugin's models migrate from core/assistant/tools/* into that plugin's contribute_agent_tools() contribution; Linda collects them at runtime through the registry, so her capability set is unchanged. The collection point (contribute_agent_tools) and the entire runtime stay in core.

## Consequences
Disabling any plugin can never disable Linda or shrink the agent runtime. The boundary baseline (scripts/core_boundary_baseline.json) shrinks without weakening the agent layer. New plugins auto-contribute their own agent tools. Any proposal to plugin-ize the assistant/agent layer is a drift violation.
