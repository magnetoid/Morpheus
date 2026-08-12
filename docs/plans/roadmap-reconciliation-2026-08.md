# Roadmap reconciliation (2026-08-12)

There are now **three** overlapping roadmaps in `docs/plans/`:

1. [`market-gap-execution-2026-08.md`](market-gap-execution-2026-08.md) — reviewed in its own appendix
2. [`comprehensive-codebase-analysis-roadmap-2026-08.md`](comprehensive-codebase-analysis-roadmap-2026-08.md)
3. [`morpheus-os-nextgen-architecture-2026.md`](morpheus-os-nextgen-architecture-2026.md)

They were written independently, none references the others, and they disagree
in places. This file reconciles them against the code so the next person plans
from one page instead of three.

---

## Where all three agree, and are right

Verified in the tree, not taken on trust:

| Finding | Status |
|---|---|
| **RBAC defined but not enforced** | Confirmed. `has_capability()` had **zero** callers outside its own app; 83 dashboard views were `@staff_member_required` only. All three rank it #1, correctly. **Phase 1 shipped v0.43.0** — the seam plus 21 money/destructive views, log-only by default. |
| **PII stored in plaintext** | Confirmed — zero `encrypt` references in `core/` or `customers/`. |
| **Audit log is mutable** | Confirmed — no hash chain, no DB-level append-only. `AuditEvent`'s docstring says *"One immutable audit row"*, which is true only by convention. |
| **No SCIM** | Confirmed — zero references. |
| **Shells import optional apps directly** | Confirmed — 27 sites. The sharpest: `/account/payment-methods/` calls **live Stripe** and `/account/orders/<n>/cancel/` issues **real refunds** with their app disabled. |
| **Tailwind Play CDN weakens CSP** | Confirmed — `'unsafe-eval'` is retained solely for the CDN's JIT. |
| **No OpenAPI / client SDK** | Confirmed. Note the distinction all three blur: `morpheus.*` is the **app-authoring** SDK. There is no HTTP client SDK and no OpenAPI schema. |

---

## Where they are wrong

**UCP already ships.** `morpheus-os-nextgen-architecture-2026.md` lists *"Lack
of Universal Commerce Protocol integration — Morpheus only supports MCP"* and
scores UCP as a Should-Have at **4 engineer-months**. But
`/.well-known/ucp.json` is live, its capabilities track enabled state, and it
has test coverage (`agentic_checkout/tests/test_mcp_cart.py`). It shipped in
v0.30.0. Budgeting a quarter of Q2 to rebuild it would be wasted.

**The App Store is not absent.** `/dashboard/apps/store/` exists with a registry
JSON and an install flow. It is an MVP browse surface, not a distribution
system — real, but thin. "No App Store" overstates the gap; "no *distribution*"
is the accurate framing.

**The GraphQL cache was not "partially mitigated."**
`comprehensive-codebase-analysis-roadmap-2026-08.md` §6 downgrades it to
partially mitigated with the remaining issue being string-heuristic
cacheability. In fact the invalidator deleted `gql:*product*` — **a prefix
nothing has ever written** — so every product edit invalidated zero keys and the
API served stale data until TTL. Fixed in v0.43.1. The doc's optimism came from
reading the caching code without checking that the delete patterns matched the
write patterns; the two files never import each other.

**Approval-gating and bulk AI content already ship** (repeated from the
market-gap review): the consent kernel, `OpsProposal` staging, and
`ai_content/services_bulk_catalog.py` are live. Scope those as UX unification,
not new capability.

---

## The structural problem: resourcing

This is the most important thing on this page.

- `comprehensive…` assumes **2 backend + 1 platform/security + 1 frontend + 0.5 PM + shared QA**.
- `morpheus-os-nextgen…` assumes **2 security + 2 backend** in Q1, then **2 frontend/UX + 1 LLM + 1 backend** in Q2, and so on.

That is roughly **five to six engineers sustained for twelve months**, plus a
CISO security review and a Merchant Advisory Board.

Morpheus is a solo project with AI assistance. Both roadmaps are written for a
company that does not exist yet. Their **sequencing** is sound — trust →
productization → ecosystem → intelligence is the right order — but the
**scale** is fiction, and a plan whose first line item needs two security
engineers will simply not start.

Re-scope to what one person can actually land: one workstream at a time, each
shippable in days, each verified in production before the next begins. That is
how v0.36 through v0.43 actually shipped.

---

## What is missing from all three

- **Distribution.** None of them covers how another person installs or updates
  Morpheus. The updater is inert on container deployments and its git channel
  cannot serve anyone else — see [`../UPDATING.md`](../UPDATING.md). Without
  this, "open core" is a licence file, not a product.
- **The CLA.** All three propose a marketplace or third-party ecosystem. None
  mentions a contributor licence agreement. Accepting outside code without one
  is the single hardest thing here to unwind later.
- **Per-app and per-theme update channels**, which is what an app ecosystem
  actually runs on.

---

## Recommended order (solo-scoped)

1. **Finish RBAC** — phase 2: reads, nav visibility, GraphQL. Phase 1 is live.
2. **Immutable audit** — hash chain + append-only. Small, and it makes an
   existing docstring true.
3. **Distribution** — signed manifest, `UpdateSource`, per-app channels.
   Unblocks everything called "ecosystem" in all three documents.
4. **P6 disable-debt** — stop live Stripe calls and real refunds from running
   through disabled apps.
5. **PII encryption** — needs care on searchable fields.
6. **OpenAPI schema** — the real prerequisite for anything named "SDK".

Everything else waits for the edition boundary and the CLA.
