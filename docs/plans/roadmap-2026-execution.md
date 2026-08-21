# Roadmap 2026 — execution plan (reality-checked)

Companion to `docs/product_roadmap_2026.md`. That document's **strategy** is
sound; several of its **premises are stale** — it was written against an older
snapshot, and building from it as written would rebuild shipped features. This
file is the fact-checked version: what actually exists, what is genuinely
missing, and the order to build it. Verified against the tree at v0.58.0.

## What the roadmap gets wrong (verified, with evidence)

| Roadmap claim | Reality |
|---|---|
| 1.3 UCP is a 6-8 week Q3 build | **Already ships.** `agent_mcp/well_known.py` serves `/.well-known/ucp.json` + `agent.json`; `agentic_checkout` serves `/.well-known/acp.json` with a working Stripe delegated-token money path and a product feed. Only `returns`/`subscriptions` capabilities advertise false. |
| §2.1 "RBAC bypassed by blanket `@staff_member_required`" | **Half-wrong.** The seam is real and shipped (`core/authz.py`: `has_capability`/`check`/`@require_capability`/`enforce`, hook-based, audited). The gap is **coverage and mode**, not existence. |
| §2.1 "shells hard-import optional plugins" | **Resolved.** The `is_active` sweep landed (v0.45.0); no module-scope optional-plugin imports remain in either shell. |
| §2.1 "incomplete checkout totals pipeline" | **Resolved.** `CART_CALCULATE_BREAKDOWN` has 8 priority-ordered subscribers with Money validation + negative clamping. |
| 1.1 sandboxing as greenfield | **Mischaracterized.** AST sandbox (denylist + curated builtins + wall-clock timeout), kill switch, daily run/spend caps, per-action price/refund caps, and a kernel-verified human-consent gate all exist. |
| 2.2 "leverage the existing bandit" | **Understated.** Thompson-sampling bandit *and* an AI merchandiser autopilot filing `MerchandisingProposal` rows into a review queue both ship. |

## The genuine gaps, in build order

### P1 — RBAC coverage (roadmap 1.2, reframed) ← **highest value**
Not "wire RBAC" — **expand it**. Today: **43** `@require_capability` sites in 7
files vs **323** `@staff_member_required` in 95 files (~13% coverage), default
`enforcement_mode='log'` (so even those 43 deny nothing), and **zero** GraphQL
resolvers consult `core/authz.py`. Work:
1. Sweep the remaining staff views onto capabilities, in plugin-sized batches.
2. Gate GraphQL resolvers on the same capability vocabulary (this subsumes the
   deferred "8 divergent GraphQL auth patterns" item from the API audit).
3. Only then consider flipping the default to `enforce`.

**The landmine that governs this work** (CLAUDE.md): *a capability no role can
hold denies EVERYONE once enforcement is on.* Every capability used in a gate
must exist in `rbac._DEFAULT_TEMPLATES` in the same change;
`core/tests/test_authz.py::CapabilityVocabularyTests` scans the tree and fails
otherwise. Because the default is `log`, the sweep is safe to land
incrementally — it records what *would* be denied without denying it.

### P2 — Agent execution boundaries (roadmap 1.1, reframed)
Present: code sandbox, budget/scope/kill-switch, money caps, consent kernel.
Genuinely absent, in value order:
1. **Network egress control** — no allowlist/SSRF guard for agent-initiated HTTP.
2. **Per-run wall-clock** at the runtime level (today's timeout is per-script).
3. **DB write scoping** — `core/db_router.py` has no agent/read-only role;
   scoping is tool-level scope strings only.
4. Process/container isolation (the sandbox module itself notes "swap the thread
   runner for a subprocess/container") — the largest, lowest-marginal-value step.

### P3 — B2B depth (roadmap 2.1)
Present: `PriceList`/`PriceListItem`, `Quote`/`QuoteLine` (7-state lifecycle +
order conversion), `NetTermsAgreement`, bulk-order pad, agent tools.
Absent: **buyer-initiated RFQ intake**, **multi-level approval chains**,
**requisition/shopping lists**, **company/buyer hierarchy**, and
**sales-rep impersonation** (zero impersonation code exists anywhere — the
roadmap is correct on this one). Note impersonation is a security-sensitive
feature: it must be capability-gated and fully audited, so it depends on P1.

### P4 — Merchandising bulk-content UI (roadmap 2.2, shrunk)
The bandit and the autopilot ship. The real missing piece is narrow: bulk AI
catalog operations (`ai_content/services_bulk_catalog.py`) exist but are wired
**only to self-improvement healers**, with no dashboard bulk-action surface;
plus the bandit→layout-suggestion linkage.

### P5 — Forecasting depth (roadmap 3.1, corrected)
"Dynamic pricing" today is a deterministic 3-branch inventory heuristic writing
`DynamicPriceRule` multipliers on the `PRODUCT_CALCULATE_PRICE` seam — no
competitor signals, no ML. Forecasting is a 28-day SMA → days-until-stockout;
**the roadmap's 180-day horizon does not exist**. Extending the horizon needs
seasonality, which needs historical depth — genuinely a later phase.

### P6 — Headless reference app (roadmap 3.2)
Correctly missing; `docs/HEADLESS.md` already documents the surface, so the
dependency is met. Lowest urgency: it serves developer adoption, not merchants.

## Sequencing note
P1 is the through-line: it is the roadmap's own Phase 1 milestone, it unblocks
B2B impersonation (P3), it satisfies the UCP risk-mitigation clause ("strictly
scope API access for external AI models"), and it absorbs an outstanding API-
audit item. Everything else is additive feature work that can follow.
