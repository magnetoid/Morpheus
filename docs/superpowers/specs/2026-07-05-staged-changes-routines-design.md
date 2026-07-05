# StagedChange (OpsProposal) + Linda Routines — Design

**Date:** 2026-07-05 · **Status:** approved (Bet 2 of the mid-2026 trends roadmap,
`docs/plans/trends-2026-adoption.md`) · **Owner:** `core/assistant/` (the model +
inbox generalize ADR-0028's propose-only queue; routines extend the existing
`agent_core` scheduler).

## Context

The market verdict of 2026: acting copilots with human confirmation compound
(Sidekick's staged workflows, Agentforce $1B ARR); unsupervised agents die in
the trough. Morpheus already has every ingredient — and three *separate*,
non-generic propose→approve mechanisms:

- `CodeProposal` (core/assistant/models.py:239) + apply.py — self-coding only,
  with the proposals inbox UI (views_proposals.py, proposals.html).
- `SiRecommendation` (core/self_improvement/models.py:126) — code-quality
  findings with approve/reject/snooze + suppression rows.
- `AgentApprovalRequest` (agent_core/models.py:263) — per-tool-call pause.

And routines half-exist: `BackgroundAgent` (agent_core/models.py:206) +
`scheduler.tick()` (every-minute beat) already run Worker prompts on an
interval, gated by the default-off `AUTONOMY_ENABLED` filter. Per-run
`token_budget` exists (base.py:65, enforced runtime.py:141). What's missing is
the **generic trust artifact**: business-level changes (price edit, SEO meta
fill, stale-product flag, feed fix) staged as a reviewable diff a merchant
approves — the "Linda Ops Inbox" already named as Wave-3 item 14 in
docs/plans/cutting-edge-open-core-2026-07.md:148.

**Goal (first slice):** one generic `OpsProposal` model + inbox, one write-tool
pathway that stages instead of writing, one demo routine — so every future
skill/routine inherits propose→preview→approve→apply for free.

## Non-goals (this slice)

- Migrating ALL existing write tools to staging (one pathway proves it; the
  rest migrate incrementally).
- Dollar-denominated budgets / tier-degradation routing (per-run
  `token_budget` suffices now; tier routing is roadmap row 7, separate).
- Merging CodeProposal/SiRecommendation into OpsProposal (they keep their
  specialized pipelines; the inbox can LIST them later — not now).
- Auto-apply policies ("auto-approve low-risk") — everything human-approved
  in v1, per ADR-0028.

## Design

### 1. `OpsProposal` model (`core/assistant/models.py`) — **one migration**

```
OpsProposal:
  id UUID · created_at · updated_at
  source        Char(80)      # 'routine:catalog-hygiene' | 'skill:<name>' | 'chat'
  agent_run     FK agent_core.AgentRun null  # provenance (run that proposed it)
  kind          Char(40)      # 'product.update' | 'seo.meta' | 'price.change' | …
  title         Char(200)     # human headline: "Fill missing meta description on 12 products"
  summary       Text          # why — the agent's rationale
  target_ct/target_id         # GenericFK to the object being changed (nullable for multi-object)
  changes       JSON          # [{object: 'catalog.product:<id>', field, old, new}, …]
  status        Char(20)      # proposed | approved | applied | rejected | expired | failed
  approved_by   FK user null · approved_at · applied_at
  apply_error   Text          # populated on failed apply
  expires_at    DateTime null # stale proposals auto-expire (data may have drifted)
```

`approve(user)` is staff-only fail-closed (mirror CodeProposal.approve);
`apply()` re-checks freshness (each change's `old` still matches the live
value — drifted rows are skipped and reported), applies through the **same
service/tool rails the agent would have used**, records `core.audit` entries,
flips status. Never raises; failures land in `apply_error`/`status='failed'`.

### 2. Staging pathway for write tools (`core/assistant/staging.py`, new)

`stage_proposal(*, source, kind, title, summary, changes, agent_run=None,
target=None) -> OpsProposal` — the single constructor every emitter uses.

First integration: the **confirmed-write ecommerce tools**
(core/assistant/tools/ecommerce_writes.py) gain a staging mode — when a run
carries `context={'staged': True}` (set by routines; chat keeps today's
AgentApprovalRequest flow), the tool records an OpsProposal instead of
executing, and returns "staged proposal <id>" to the LLM. This is a *mode on
the existing tools*, not new tools — `core/safety.py` class-blocklist checks
(`is_class_allowed`) run at STAGING time too, so a forbidden class
(`pricing_change` etc.) can't even be proposed.

### 3. Inbox UI (extend the existing proposals surface)

`/dashboard/assistant/proposals/` (views_proposals.py) gains a second tab/
section: **Ops proposals** — card per OpsProposal modeled on the existing
`proposals.html` `<details>` card: title, source badge, summary, and a
field-level before→after table rendered from `changes` (plain table, not a
code diff — these are data changes), Approve/Reject buttons (POST to a new
`ops_proposal_action` handler with the same permission posture: staff for
reject, staff for approve+apply since these run through class-allowlisted
rails — superuser NOT required, unlike CodeProposal which lands code).
An `ACTIVITY_FEED` filter subscriber surfaces pending-proposal counts on the
dashboard home.

### 4. Demo routine: nightly catalog hygiene

A `BackgroundAgent` seeded via a data-less path (management command or a
"Create routine" preset in the existing agent_core dashboard page):
`agent_name='worker'`, prompt = "Scan the 20 most recently added active
products for missing meta descriptions, empty short descriptions, or missing
alt text; STAGE fixes via your write tools; do not modify anything directly.",
`context_overrides={'staged': True}`, `interval_seconds=86400`,
`token_budget` set (e.g. 60k). Runs through the existing scheduler +
AUTONOMY_ENABLED gate (still default-off — the merchant flips autonomy on
deliberately, per ADR-0028).

### 5. Costs (visibility only, this slice)

The inbox card shows the proposing run's `AgentRun.estimated_cost_usd` — the
"this routine cost $0.11 and staged 12 fixes" retention metric. No new budget
machinery.

## Contract & safety

- OpsProposal lives in core/assistant (the assistant layer is core per
  CLAUDE.md; the self-improvement/safety loop is explicitly core). The
  migration rides core/assistant's existing migration dir. Additive only.
- Apply path re-uses tool/service rails + `core.audit` — no new write
  surface; `core/safety.py` consulted at staging AND apply.
- Plugins later contribute proposal kinds via their own tools — nothing in
  this slice imports plugin models from core (the changes JSON references
  objects by label+id; apply resolves via ContentType, which is
  Django-generic, not a plugin import).
- Disable/kill switches: routines inherit AUTONOMY_ENABLED (default off);
  staging mode only activates via explicit run context.

## Verification

- Unit: stage_proposal creates a proposed row; safety class-blocklist blocks
  a forbidden kind at staging; approve() permission fail-closed; apply()
  happy path mutates the target + audits + flips status; apply() with
  drifted `old` skips that change and reports; apply failure → failed +
  apply_error; expired proposals refuse approve.
- Tool-mode: ecommerce write tool with `staged: True` context creates a
  proposal and does NOT mutate; without it, behavior unchanged
  (AgentApprovalRequest flow intact — regression-tested).
- View: proposals page lists ops proposals; POST approve applies and
  redirects; permission boundary tests (anonymous/non-staff blocked).
- Routine: scheduler fire with the demo BackgroundAgent (mock provider)
  produces ≥1 OpsProposal and zero direct writes.
- Suites: core/assistant + agent_core + admin_dashboard green; `migrations`
  job note: the new migration is additive (no FK retargets); ruff clean.
