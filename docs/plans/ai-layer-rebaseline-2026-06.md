# AI Layer — Re-baselined Remaining-Work Plan (2026-06)

The earlier roadmap (`Linda Assistant + Agent System`) is **~70% already
executed**. This document replaces it with an accurate map: what's done (so we
don't redo it) and the genuine remaining gaps, prioritized. Every claim below was
verified against the code on 2026-06-17.

---

## Already done — do NOT rebuild

| Area | Proof |
|---|---|
| **Phase 0** Provider decoupling | `core/agents/provider_registry.py` (register/get_provider_config/get_active_provider_name); `llm.py` + `consensus.py` resolve via the registry; `ai_assistant.ready()` registers its resolver. Remaining core→plugin imports are lazy/guarded. |
| **Phase 1** Kernel tests | `test_runtime.py` (12), `test_policies.py` (7), `test_llm.py` (8), `test_skills.py` (8), `test_provider_registry.py` (5), `agent_mcp/tests/test_servers.py`. Covers run loop, scope-deny, approval-reject, max_steps, budget, MCP Bearer scope. |
| **Phase 2** Self-dev dashboard | `agent_core/views.py` selfdev_list/detail/action; `core/assistant/apply.py` preflight/apply_proposal/`revert_branch`; consensus.evaluate; all safety gates intact (`MORPHEUS_SELF_UPDATE_ENABLED`, superuser approve, 2/3 quorum, 5/24h, `core/safety.py`, branch-only plumbing). |
| **P3** flags (2 of 5) | `enable_intent_engine` (intent.py:74) + `enable_semantic_search` (plugin.py:479) WIRED. |
| **P4.1** Budget | `enforce_budget` called at `runtime.py:141`; tested. |
| **P4.2** Compaction (agent runtime) | `core/agents/compaction.py` + called at `runtime.py:135`; `test_compaction.py`. |
| **P5.1** Per-conversation cost | `AssistantConversation.cost_summary()` + persisted tokens. |
| **P5.2** Agent-run viewer | `/dashboard/agents/observability/` + `/runs/<id>/`. |
| **P5.4** Background-agent CRUD | `BackgroundAgent` model + `/dashboard/agents/background/` create/edit/pause. |

---

## Remaining work — real gaps, prioritized

### Tier A — small, safe, high-clarity (quick wins) — ✅ DONE (2026-06-17)

> Shipped: A1 (`llm.py` parse_error surfacing + runtime `_tool_back`), A2
> (`RevertTests` + non-superuser apply/reject/revert boundary tests), A3
> (stale provider-config import fixed). 55 tests green.


**A1. Surface malformed tool-arg JSON (P4.4).** `core/agents/llm.py:213-216`
(OpenAI provider) silently falls back to `{}` on `JSONDecodeError`, so the LLM
gets no signal it sent bad args. → push a `TraceStep`/tool-error instead (or at
least log). Mirror in the Anthropic path if present. *Verify:* a unit test in
`test_llm.py` asserting the error surfaces. *Risk: very low.*

**A2. Self-dev dashboard test gaps (Phase 2).** Code is complete + safe-by-gates,
but untested paths: (a) `revert_branch()` has **zero** unit coverage
(`core/assistant/tests/test_apply.py` — add a `RevertTests`: apply→revert →
status back to `approved`, `selfdev/*` branch deleted, HEAD untouched);
(b) dashboard perm-boundary tests only cover *approve* — add non-superuser
**apply/reject/revert** rejection tests in `test_selfdev_dashboard.py`.
*Risk: near-zero (tests only).*

**A3. Phase 0 nit.** `core/assistant/tests/test_self_learning.py:20` imports
`get_provider_config` from `plugins.installed.ai_assistant.services.config`
instead of `core.agents.provider_registry`. One-line fix. *Risk: none.*

### Tier B — capability wiring (Phase 3), one flag per PR

**B1. `enable_zero_shot_catalog`. — ✅ DONE (2026-06-17).** `services/zero_shot.py`
implemented (fail-soft generic classifier + `classify_product`); exposed as the
flag-gated `catalog.classify_product` tool; schema text updated; 9 tests.

**B2/B3 — still open, need a decision (see below).**

**B1 (original spec).** `services/zero_shot.py` is an **empty stub**
(`# zero_shot service`); flag is defined but never read. Note: `book_product`
already shipped an AI `classify_books` command (git `2a22856`) — reuse that
classifier rather than build new. Implement the service, gate it in
`ai_assistant.contribute_agent_tools()` (mirror `enable_semantic_search` at
plugin.py:479), expose as a flag-gated tool. *Verify:* off → tool absent; on →
callable against real catalog. *Risk: low (default-off).*

**B2. `enable_autonomous_operator`.** `services/operator.py` is a back-compat
shim, unreachable; flag never read. **Decide activation model first** —
recommend gating proactive `BackgroundAgent` execution in
`agent_core/scheduler.py:85` (the operator concept = autonomous background runs),
NOT a new tool. Wire the flag as the master enable for proactive runs. *Risk:
medium — touches the autonomous loop; default-off, draft/observe before act.*

**B3. `enable_synthetic_testing`.** DORMANT **and mis-scoped**: `services/probe.py`
is provider-connectivity probing, not store smoke tests. Needs a scope decision
(automated store smoke tests = new `services/synthetic_testing.py`, or repurpose
+ rename the flag). Lowest priority — ambiguous, define before building.

### Tier C — reliability + UX (medium)

**C1. Compaction in Linda's loop (P4.2c). — ✅ DONE (2026-06-17).** `Assistant.stream`
now runs `compact(...)` at the top of each step with a provider-backed
`_summarize_history` summarizer (guarded against a kernel-import failure). 2 tests.

**C2. LindaMemory editor (P5.3).** `LindaMemory` model exists
(`core/assistant/models.py:78`) but is tool-write / turn-start-read only — no UI.
Add superuser-gated CRUD (list/edit/delete) as an `agent_core` (or ai_assistant)
dashboard page contribution. *Risk: low — new views, no migration.*

### Tier D — larger / riskier (own PR + design care)

**D1. Sandbox subprocess isolation (P4.3).** `core/agents/sandbox.py` still runs
`exec()` in a **daemon thread** that can't be killed (leaked-thread backstop caps
at 5). Design doc already written: `docs/plans/sandbox-subprocess.md`. Implement
the hard-killable subprocess + AST validation + resource limits; `test_sandbox.py`
is the regression gate. *Risk: med-high.*

**D2. Proactive drafting (P5.5).** The self-dev dashboard + approval flow exist,
but nothing auto-creates `CodeProposal` rows from observed errors/opportunities.
Add a **draft-only**, dev-mode-gated trigger in Linda's runtime; apply stays
owner + `MORPHEUS_SELF_UPDATE_ENABLED` gated. *Risk: med — keep strictly
draft-only.*

**D3. Tool migration (cross-cutting).** `core/assistant/tools/ecommerce.py` +
`ecommerce_writes.py` still query catalog/orders models directly (wrong layer).
Migrate to `orders`/`catalog` `contribute_agent_tools()`; **tool names must stay
stable** so Linda's prompts/skills keep resolving. Slot opportunistically when a
domain plugin is already being touched. *Risk: med — behavior-preserving refactor.*

---

## Suggested sequence

`A1 → A2 → A3` (safe warm-up, all shippable independently) → `B1` (clear,
reuses existing classifier) → `C1`/`C2` → then the Tier-D items each as their own
carefully-reviewed PR. `B3` only after its scope is defined. Never land two
prod-affecting merges in rapid succession (Coolify thrash). Each item green on
`sqlite:///:memory:` + the CI Postgres `migrations` job; code + docs ship together.
