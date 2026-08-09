# Kernel-hardening proposal — evaluation & decision

**Date:** 2026-08-09
**Input:** an external "Morpheus Platform Kernel Hardening Proposal" (v0.x → v1.0),
proposing Commands/Queries/Events primitives, a unified agent kernel, a
PlatformGraph, an EventEnvelope+outbox, server-side approvals, supply-chain
locking, and a tool-output contract.
**Method:** two parallel investigations — (a) grounding every claim about the
*current* architecture against the actual code, (b) 2026 best-practice research
on each proposed pattern for a small self-hosted AI-native commerce platform.
**Verdict in one line:** adopt the *spine* (one governed door for agent writes);
defer or skip the *machinery*. Much of the proposal describes capabilities
Morpheus already ships.

---

## 1. The correction that reframes everything

The proposal argues, in several sections, for building things that **already
exist** in Morpheus. Grounded findings:

| Proposal wants to build… | Reality in tree | Evidence |
|---|---|---|
| Server-side approval records (not an LLM boolean) | **Exists** | `core/agents/models.py` `AgentApprovalRequest` — `args_fingerprint` (sha256 bound to one call), single-use `consumed_at`, fail-closed (`approval_registry.check` denies until a resolver is registered) |
| Structured tool output (model-context vs display vs raw) | **Exists** | `core/agents/tools.py` `ToolResult(output, display, metadata)`; metadata explicitly never sent to the LLM |
| Production lockfile + supply-chain | **Mostly done** | `requirements.lock.txt` (uv `--generate-hashes`), `pip-audit` enforcing in CI, bandit, dependabot |
| Transactional outbox | **Scaffolded** | `OutboxEvent` model + `transaction.on_commit` webhook dispatch (writes only when `NATS_URL` set) |
| Contribution ownership + active-gating | **Exists** | `register_hook(..., plugin=self.name)` + `HookRegistry._owner_inactive` wired to `is_active` |
| Core→plugin boundary CI gate | **Exists** | `scripts/check_core_boundary.py`, ratchet at 0 |

Consequence: do **not** spend a v1.0 budget rebuilding solved problems. The
proposal's value is the handful of *genuinely-missing* items below.

---

## 2. The spine — genuinely smart, grounded in real defects

These three are the payload. Each maps to an actual hole the grounding found.

### 2.1 Close the Assistant enforcement asymmetry (the real "one kernel")
The proposal's "two duplicated security loops" framing is **wrong** — but the
truth is more actionable. There are two loops (`core/agents/runtime.py` = Worker,
`core/assistant/runtime.py` = Linda) and they are **asymmetric, not duplicated**:

| Enforcement | Worker | Linda (Assistant) |
|---|---|---|
| Kill switch | ✅ | ✅ |
| Scope check (`enforce_policy`) | ✅ | ❌ (relies on mode tool-palette filter) |
| Approval gate | ✅ fail-closed | ❌ none in `_dispatch_tool` |
| Token budget | ✅ | ❌ |
| Deadline | ✅ | ❌ |
| Daily circuit-breaker | ✅ | ❌ |

Linda enforces only the kill switch + mode-based tool filtering + *post-hoc*
audit. **Fix:** route Linda's tool dispatch through the same enforcement stack,
with degraded/fallback behavior as a *policy config object*, not a second code
path (the moment fallback becomes a second `while` loop, the single
enforcement-point is lost). Highest security value on the list. Effort: M
(refactor, not a bolt-on).

### 2.2 Kill the refund Path-B divergence — **downgraded after reading the code**
Original claim: "two copy-pasted bypasses of RefundService." **On inspection this
is overstated.** The money path is *already* well-consolidated: the `orders.refund`
agent tool, the returns dashboard view, and storefront self-service all funnel
through `RefundService.process` (cap + idempotency + gateway). The two "Path-B"
sites — `orders.mark_refunded` agent tool (`agent_core/tools/orders.py`) and
`mark_order_refunded` GraphQL mutation (`orders/graphql/mutations.py`) — are
**intentional flag-only** operations for refunds processed *outside* Morpheus
(Stripe/bank). Routing them through `RefundService` would fire a **second real
refund** — a bug, not a fix. The only genuine nits:
- 6 lines of identical raw-update logic duplicated across the two sites (minor DRY).
- A scope inconsistency: the tool requires `orders.write`, the mutation requires
  `orders.cancel` — same logical op, two scopes.

Neither is a security hole (both gated: approval / staff scope; no money moves).
**Recommendation:** optional small dedup into one `Order` helper + a deliberate
scope decision — **not** a "consolidate onto RefundService" change. Low priority.
*(This is the honest correction to the initial synthesis.)*

### 2.3 Plugin-A-cannot-import-plugin-B CI guard — **shipped-ready**
CLAUDE.md states the rule advisorily; only core→plugin was enforced. Built as
`scripts/check_plugin_boundary.py`: **requires-aware** baseline-and-ratchet — a
plugin may import a sibling only if it declares it in `requires`; NEW *undeclared*
cross-plugin imports (and stale baseline entries) fail CI. Current baseline: **122
undeclared pairs** (337 import statements; 55 pairs already legitimately declared).
Surfaces real smells (e.g. `catalog → book_product`, `catalog → orders` — a base
importing verticals). Effort: S. **Repay from the baseline over time.**

---

## 3. Smart-but-later — take the cheap half, skip the expensive half

- **EventEnvelope + correlation-id: yes. Full outbox relay: no.** Adding
  `event_id`/`correlation_id`/`causation_id`/`schema_version` to hook payloads is
  near-free and immediately improves audit/tracing (ties agent-run → tool-call →
  order mutation). The outbox *machinery* solves the dual-write problem, which
  only bites with real external cross-process consumers — and the NATS drainer
  isn't even in-tree. Adopt the envelope now; defer the relay until a first real
  subscriber. (Payloads today are plain dicts — `core/hooks.py` `_serialize_payload`.)
- **PlatformGraph as boot-time validation: yes. As live source-of-truth + COW
  swap: no.** A startup check for duplicate hook/tool names, dependency cycles,
  and undeclared deps — over manifests you already have — catches exactly your
  historical bugs (duplicate `ReturnRequest`, double-registered hooks). But making
  an immutable graph the *live* dispatch structure would sit beside the Django app
  registry and the hook bus's `is_active` gate as a **second source of truth** —
  the "one concept, two owners" bug the codebase already avoids (the `deactivate()`
  landmine shows the chosen model is gate-on-`is_active`, not rebuild-a-graph).
- **Aggregate/top-N/cursor tool outputs.** `ToolResult` structure is done, but
  large results are dumb-truncated at 8000 chars (`runtime.py`). Returning
  count/aggregate/cursor is worth doing incrementally, per high-volume tool.

---

## 4. Skip / premature

- **Command/Query *bus* (dispatch + Command/Handler objects).** The *goal* — one
  governed seam per capability — is right and largely already embodied by services
  like `RefundService`. But a bus fights Django (resolvers/views *are* the
  application layer) and hurts the legibility that matters most in an AI-assisted
  codebase. Formalize the seam as plain service functions + decorators; don't add
  message dispatch. (Recognized pattern: application-service layer, *not* CQRS —
  and real CQRS means separate read/write models, which we explicitly don't want.)
- **Full transactional-outbox relay/inbox tables.** No external consumers yet.
- **A big typed `ExecutionContext` dataclass threaded everywhere.** The `context`
  dict works; the only concretely-missing keys are `actor` and
  `request_id`/`correlation_id`. Add those two; skip the ceremony.

---

## 5. Recommended sequence

The spine is one bet from three angles — *one governed door for agent writes* —
and compounds if sequenced together:

1. **Plugin-boundary guard** (§2.3) — built, S, low-risk. Ship first (own deploy).
2. **EventEnvelope + correlation-id** (§3) — cheap, unlocks tracing/audit. 
3. **Linda enforcement parity** (§2.1) — the security payload; M, needs care +
   contract tests proving parity with the Worker.
4. Boot-time PlatformGraph *validation* (§3) — when convenient.
5. Refund dedup + scope decision (§2.2) — optional, low priority.

**Explicitly do not build:** command/query bus, outbox relay, COW live graph,
approval records (exist), structured ToolResult (exists), lockfile (exists).

## 6. Sources
- Cosmic Python ch.12 (CQRS ≠ read replicas); CodeOpinion "Read Replicas Are NOT CQRS" (2025).
- Anthropic "Writing tools for agents" (Sept 2025) — tool-output pagination/truncation.
- LangChain human-in-the-loop docs (2025–26) — server-side approval records.
- Transactional Outbox trade-offs (softwarecraftsperson.com, 2025-10); event-driven.io outbox/inbox.
- Backstage new backend system; Home Assistant integration manifest — plugin-graph precedent.
- Astral uv lockfile/SBOM export; Trivy vs Grype (2026) — supply chain.
