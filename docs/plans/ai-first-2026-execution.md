# AI-First 2026 — Execution Plan (re-baselined)

Supersedes `docs/analysis/ai_first_platform_proposal_2026.md` for *execution*.
The proposal's audit is sound (verified: every cited path/plugin exists, no
hallucinated refs, honest "no invented metrics" methodology). This doc adjusts
it for what shipped in the June-2026 agent/storefront sprint and turns the
12-feature wishlist into an ordered **spine** you actually build.

## Principle

Build the spine in order; don't chase all 12 features. Spine:
**finish measurement → finish security → one signature shopper experience →
one signature merchant workflow → then measure before expanding.**
Each move ships as plugin contributions, tested, behind the existing gates.

## Re-baseline: proposal gaps already (partly) closed this sprint

| Proposal item | Status now | Evidence |
|---|---|---|
| F9 AI cost governance ("cannot explain cost") | **~40% done** | `core/agents/pricing.py` + per-run cost + Est-cost insights view |
| F5 recommend→approve→execute ("advisory only") | **pattern shipped** | self-dev approval dashboard (codegen→consensus→apply) |
| F10 API-key lifecycle | **done** | `agent_mcp` tokens SHA-256 hashed |
| §1 core↔plugin AI boundary | **provider config decoupled** | `core/agents/provider_registry.py` (tools still import models — open) |
| F11 "request/response only" | **overstated** | SSE streaming exists for assistant + agent runs |

So Phase-0 ("stabilize the base") is *smaller* than the proposal assumes, and the
biggest genuine hole remains the **shopper AI wedge (F1)**.

---

## Move 1 — Finish F9: AI cost & eval governance *(small; do first)*

**Why first:** instruments every later AI bet; cheap; builds on shipped work.
**Scope (each a small PR):**
- Per-conversation cost on Linda's chat (persist `AssistantRunResult` tokens →
  display "$/tokens" per conversation). *Mind the sqlite/Postgres FK landmine.*
- Tool success/failure rate + p95 latency columns in
  `/dashboard/agents/observability/` (data already on `AgentStep`/`AgentRun`).
- Surface the token-budget cap (`agent.token_budget`, already enforced) in the UI.
**Reuse:** `core/agents/pricing.py`, observability view, `AgentRun`/`AgentStep`.
**Done when:** a merchant can see cost + success rate per AI workflow.

## Move 2 — F10 security: MFA + lockout + audit surface *(medium; proposal-Critical)*

**Scope:**
- **MFA as a plugin** (house rule — auth stays simple in core; SSO/MFA/RBAC are
  plugins). TOTP enrol/verify for staff; gate `/dashboard`.
- Explicit **account-lockout** config (allauth has default rate-limiting; make it
  intentional + documented).
- **Audit-log operating view** for AI actions (`core/audit` already records
  `agents.decision`, `selfdev.apply`, etc. — add a filterable dashboard page).
**Reuse:** `core/auth`, `rbac`, `core/audit`, hashed `agent_mcp` tokens.
**Done when:** staff can enrol MFA; AI actions are reviewable in one place.

## Move 3 — F1: the shopper AI wedge (`ai_stylist`) *(the big one; spec first)*

**The genuine hole.** `ai_stylist` is a ~140-LOC storefront chat shell with no
real conversational intelligence. Make it a first-class shopper assistant:
discovery, comparison, gifting, bundle-building, product Q&A.
**Build on what now exists:** the agent runtime (`core/agents`), the
`catalog.semantic_search` tool (wired this sprint), recommendations,
`product_stories`, `wishlist`. Storefront chat panel already contributes a block.
**Approach:** write `docs/plans/shopper-assistant.md` first (audience='storefront'
Worker + a `storefront` skill bundle of read-only catalog/cart tools; scoped so it
can browse + recommend but not mutate). Multi-week; ship behind a flag.
**Done when:** a shopper can have a real product conversation that adds to cart.

## Move 4 — One merchant approve→execute workflow (F5, concretely)

Don't build "autonomous ops" broadly. Pick **one** task (inventory reorder *or* a
merchandising tweak) and run the **self-dev dashboard pattern**: recommend →
simulate → owner approves → execute → audit. Reuse the approval-UI + gating
shape already shipped. Proves the loop without widening blast radius.

## Then: stop and measure (Move 1 pays off), before expanding

Only after the spine: F2 (customer graph — needs F1 as a consumer), F6
(forecasting — `forecasting.py` exists), F4 (content studio), F7 (B2B quotes),
F8 (omnichannel). 

## Skip / downgrade
- **F11 real-time** — SSE already covers the assistant; deprioritize websockets.
- **F12 i18n/a11y** — real but not a wedge; batch later.
- **F3 predictive ranking** — fold into Move 3/measurement; not standalone yet.

## Cross-cutting (carry from the agent roadmap)
Still-open foundational items in `docs/plans/`: context-summarization,
subprocess-sandbox, `core/assistant/tools` → plugin migration, newsletter
broadcast. Slot these opportunistically; none block the spine.

## Verification discipline (unchanged)
Every move: `ruff` + `manage.py check` + `makemigrations --check` +
`DATABASE_URL='sqlite:///:memory:'` tests; CI Postgres gate for migrations;
smoke the live URL after deploy; ship in small batches (Coolify = prod deploy).
