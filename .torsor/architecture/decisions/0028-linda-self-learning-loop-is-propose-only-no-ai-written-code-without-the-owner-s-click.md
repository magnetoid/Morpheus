---
type: decision
status: accepted
tags:
- adr
links: []
created: '2026-07-03T02:48:25'
updated: '2026-07-03T02:48:25'
rules:
- rule: AI-drafted code (CodeProposal) must never be applied to a git branch without
    a recorded superuser approval, and must never be merged to main automatically.
  guard: "grep for apply_proposal call sites \u2014 all must be behind proposal.approve()\
    \ + apply_enabled()"
- rule: Proactive assistant runs (briefing, flywheel, reflection) must skip when the
    resolved provider is mock/unconfigured and must never raise into their caller.
  guard: core/assistant/{reflection,briefing,flywheel}.py return-dict fail-soft pattern
---

# ADR 0028: Linda self-learning loop is propose-only: no AI-written code without the owner's click

## Context
v0.2.27 wired Linda's dormant self-improvement primitives into a live loop: query-aware semantic memory injection (single injection point in runtime._format_recent_memories; the old duplicate [MEMORY] block in build_system_prompt is removed), a post-run reflection pass on every spawned Worker (lessons → LindaMemory 'inferred', verdicts → record_skill_outcome counters + auto-retire, capability gaps → tool_gap.* memories), an opt-in daily briefing (read-only-scoped Worker, actions deep-link to chat via ?ask=, never auto-executed), a weekly tool-gap flywheel that drafts CodeProposals, a superuser approval queue at /dashboard/assistant/proposals/, and an evals harness (20 golden tasks, manage.py run_assistant_evals). The owner explicitly chose the lowest autonomy tier for self-coding.

## Decision
The self-coding loop is PROPOSE-ONLY. Linda may draft tool source (code.draft_tool / flywheel), the consensus panel may review it, but code reaches a git branch only after a superuser clicks Approve in the proposals queue AND MORPHEUS_SELF_UPDATE_ENABLED is set — and never reaches main by any automated path. Reflection/briefing/flywheel must be fail-soft (never affect the run or crash-loop rows) and skip entirely when no real LLM provider is configured. The daily briefing Worker runs with scopes filtered to *.read only. Auto-retire of learned skills goes through the single owner record_skill_outcome (no parallel counter logic).

## Consequences
Raising Linda's autonomy tier (auto-branch or auto-merge) is an ADR-level change requiring explicit owner sign-off, not a config tweak. Any new proactive agent surface must follow the same shape: read-only scopes, opt-in StoreSettings switch, actions routed through Linda's confirmed-write gates. The evals harness is the regression baseline for prompt/skill/memory changes — run it before shipping assistant changes once a provider is configured.
