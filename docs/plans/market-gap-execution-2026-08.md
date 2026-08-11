# Morpheus OS — Market Gap Execution Plan (2026-08)

**Status:** DRAFT PLAN — execution not started.
**Source inputs:** [`docs/analysis/missing-capabilities-market-gap-report-2026-07.md`](file:///Users/magnetoid/coding/morph/docs/analysis/missing-capabilities-market-gap-report-2026-07.md), [`docs/analysis/enterprise_benchmark_gap_report_2026.md`](file:///Users/magnetoid/coding/morph/docs/analysis/enterprise_benchmark_gap_report_2026.md), [`docs/analysis/comprehensive_application_audit_2026-07.md`](file:///Users/magnetoid/coding/morph/docs/analysis/comprehensive_application_audit_2026-07.md)

**Plan intent:** convert the market-gap analysis into a build sequence that is honest about what already ships, prioritizes the highest-adoption gaps, and turns Morpheus's existing AI substrate into merchant-visible product value.

---

## Executive Direction

Morpheus already has a stronger AI and plugin kernel than any direct competitor, but the platform still under-monetizes that advantage. The execution priority is:

1. **Productize what already exists**: unify and elevate Linda, AI content, analytics, and merchandising into merchant-facing workflows.
2. **Close enterprise trust gaps**: RBAC enforcement, SCIM, immutable audit, PII encryption, and SOC 2 readiness.
3. **Start the ecosystem flywheel**: SDK + marketplace MVP so Morpheus stops being a closed set of internal plugins.

This plan intentionally uses the **fact-check addendum** in the source report as the baseline. That means we do **not** plan work for claims that were later proven wrong. Example: merchant-facing AI surfaces do exist; the real gap is a unified, approval-gated, branded AI product layer.

---

## Corrected Baseline

Before sequencing work, these source-report corrections materially change the plan:

- **AI content generation is not missing.** Product-level and bulk AI content tooling already ships. The gap is a unified content and marketing suite.
- **Linda already has a merchant-facing surface.** The gap is a scoped, approval-gated multi-step copilot, not a first-time chat UI.
- **PDF generation exists in parts of the product.** The real gap is reporting/invoice/export PDF coverage.
- **A Python SDK exists.** The real gap is generated SDKs, OpenAPI, and a developer platform story.
- **Search analytics data exists in pieces.** The real gap is a dedicated search analytics dashboard and action layer.

This plan therefore focuses on **missing product capability**, not re-building working surfaces under a false premise.

---

## Strategic Goals

### G1. Turn AI infrastructure into merchant value

Morpheus should feel like an AI-native commerce operating system, not a platform with powerful backend primitives hidden behind fragmented admin tools.

### G2. Become enterprise-review passable

The platform should pass a serious security and operations review without relying on aspiration or roadmap promises.

### G3. Build a scalable growth model

An app ecosystem, generated SDKs, and developer onboarding are required if Morpheus is going to compound adoption like Shopify or Adobe rather than growing only through core shipping velocity.

---

## Prioritization Rules

Every phase in this plan follows these rules:

- **Exploit existing strengths first.** Prefer features that build on current agent, analytics, hooks, and plugin infrastructure.
- **No duplicate systems.** If a surface exists, improve and unify it instead of creating a parallel one.
- **Plugin-native by default.** New feature code lives in plugins and contributes into shells via hooks/blocks/pages.
- **One phase = one shippable batch.** Each phase should be releasable and measurable on its own.
- **Enterprise blockers outrank novelty.** Security and trust work can delay ecosystem work if they block adoption.

---

## Phase Overview

| Phase | Theme | Outcome |
|---|---|---|
| P0 | Baseline & truth | Lock the corrected scope and remove plan ambiguity |
| P1 | AI productization | Merchant-visible AI suite with a unified experience |
| P2 | Reporting & intelligence | Actionable analytics, exports, report builder, search insights |
| P3 | Enterprise trust | Security, identity, audit, and compliance readiness |
| P4 | Ecosystem platform | SDK, marketplace MVP, developer onboarding |
| P5 | Collaboration & workflow | Approval flows, staging, visual automation |
| P6 | Advanced optimization | Dynamic pricing, fraud scoring, peer benchmarking, live commerce |

---

## Phase P0 — Baseline Lock

**Goal:** remove ambiguity from the source report and turn the corrected analysis into an implementation baseline.

### Scope

- Reclassify already-shipped AI surfaces as foundations, not gaps.
- Convert the 15-capability report into a canonical backlog with three states:
  - `shipped_foundation`
  - `missing_core_gap`
  - `later_differentiator`
- Link every planned feature to concrete existing files/plugins that will own the work.

### Deliverables

- Backlog table added to this plan with ownership and status.
- Corrections cross-linked to the source analysis.
- Phase success metrics defined for every later phase.

### Success

- No planned item remains based on a disproven premise.
- Every future phase item has an owning plugin or clearly-defined new plugin boundary.

---

## Phase P1 — AI Productization

**Goal:** turn Morpheus's AI substrate into a coherent merchant-facing product suite.

### P1.1 Linda Copilot Upgrade

**Current truth:** Linda chat already exists. The missing layer is approval-gated, scoped, multi-step execution with merchant-safe workflows.

**Work:**

- Unify existing Linda entry points into a branded admin copilot experience.
- Add approval-gated action plans for high-risk operations.
- Expose multi-step merchant tasks using existing tools and agent runtime.
- Add reusable prompt templates for commerce operations:
  - promotions
  - stock actions
  - reporting queries
  - merchandising suggestions

**Acceptance:**

- Merchant can ask Linda to complete a multi-step admin task and receive a preview/approval step before writes.
- Audit trail clearly records proposed vs approved vs executed action.

### P1.2 Unified AI Content Suite

**Current truth:** AI content tooling exists in multiple places. The gap is fragmentation and lack of a merchant-grade workflow.

**Work:**

- Create one AI content workspace for:
  - product descriptions
  - rewrites
  - translations
  - SEO fields
  - campaign copy
- Reuse existing brand-voice settings instead of inventing a new model.
- Add batch processing and review queues.
- Add content provenance markers so merchants know what was AI-generated and edited.

**Acceptance:**

- Merchant can run single-item and batch content generation from one coherent UI.
- Generated content respects configured brand voice and supports review before publish.

### P1.3 Visual Merchandising Workbench

**Current truth:** dynamics/bandit infrastructure exists, but merchant control is not visual enough.

**Work:**

- Build a visual merchandising interface on top of existing ranking/proposal systems.
- Show AI recommendation rationale using current performance/bandit signals.
- Support drag-and-drop override and scheduled experiments.
- Add category/grid preview workflows instead of list-only proposal review.

**Acceptance:**

- Merchant can preview AI-recommended layout/ranking changes visually and override them.
- AI suggestion rationale is visible in plain language.

### P1 Success

- Morpheus has a coherent AI product story visible in the admin.
- Existing AI features feel integrated, not scattered.
- Merchant can complete real merchandising/content/admin tasks without dropping into disconnected screens.

---

## Phase P2 — Reporting & Intelligence

**Goal:** upgrade analytics from strong operational telemetry to merchant-decision infrastructure.

### P2.1 Report Builder MVP

**Work:**

- Build custom report creation using existing analytics models and KPIs.
- Support saved reports, date-range filters, and exportable report definitions.
- Add scheduled report execution for the existing export model.

**Acceptance:**

- Merchant can create and save a custom report without code.
- Scheduled reports actually run and deliver exports.

### P2.2 PDF Reporting & Document Coverage

**Current truth:** PDF is not absent globally; reporting and invoice/report PDFs are the real gap.

**Work:**

- Add report PDF rendering.
- Add invoice/export PDF paths where currently absent.
- Standardize a shared PDF rendering pattern so document generation is not plugin-specific drift.

**Acceptance:**

- Reports can be exported as PDF.
- Planned invoice/report documents use a consistent PDF pipeline.

### P2.3 Search Analytics Dashboard

**Current truth:** the platform captures search-related data, but the merchant action layer is incomplete.

**Work:**

- Create a dedicated search dashboard:
  - top searches
  - zero-result searches
  - search CTR
  - search conversion
  - missed-demand opportunities
- Surface AI suggestions such as synonym/category/content recommendations.

**Acceptance:**

- Merchant can identify top zero-result searches and act on them from a dedicated dashboard.

### P2.4 Peer Benchmarking Foundation

**Work:**

- Define privacy-safe benchmarking data model and cohorting rules.
- Start with internal architecture and data contracts even if public benchmark rollout comes later.

**Acceptance:**

- Benchmarking architecture is designed with privacy boundaries and rollout criteria defined.

### P2 Success

- Morpheus moves from prebuilt dashboards to merchant-configurable intelligence.
- Analytics findings are tied to decisions, not just charts.

---

## Phase P3 — Enterprise Trust

**Goal:** remove adoption blockers that would fail a serious enterprise review.

### P3.1 RBAC Enforcement

**Current truth:** RBAC exists as data and services but is not enforced consistently in views/resolvers.

**Work:**

- Add real capability enforcement across dashboard views, GraphQL, and sensitive actions.
- Introduce reusable decorators/mixins/helpers instead of ad hoc staff checks.
- Add scoped tests for capability and channel/org boundaries.

**Acceptance:**

- A staff user without capability cannot access or mutate protected resources, even if `is_staff=True`.

### P3.2 PII Encryption & Secret Hygiene

**Work:**

- Encrypt sensitive customer data at rest.
- Define search/hash strategy for encrypted searchable fields where needed.
- Standardize secret masking and storage expectations across settings surfaces.

**Acceptance:**

- Sensitive PII no longer persists in plaintext.
- Existing merchant UX for secrets remains masked and write-only.

### P3.3 Immutable Audit & Tamper Evidence

**Work:**

- Make audit logs append-only at the database layer.
- Add tamper-evident chaining/hashing.
- Support export and retention policy design.

**Acceptance:**

- Audit rows cannot be mutated through normal app paths.
- Tamper evidence is test-covered and exportable.

### P3.4 SCIM + Enterprise Identity

**Work:**

- Add SCIM provisioning/deprovisioning.
- Prepare for multi-IdP support in a later or parallel slice.
- Keep SSO settings aligned with masked-secret conventions.

**Acceptance:**

- Enterprise identity provider can provision and deactivate users automatically.

### P3.5 SOC 2 Readiness Track

**Work:**

- Document control gaps.
- Identify app-layer remediation required before formal readiness work.
- Pair technical changes with operational requirements instead of pretending code alone solves certification.

**Acceptance:**

- Morpheus has a concrete SOC 2 readiness checklist tied to completed engineering work.

### P3 Success

- Morpheus no longer depends on “we can fix that later” for core enterprise trust concerns.

---

## Phase P4 — Ecosystem Platform

**Goal:** make Morpheus extensible by outsiders, not just internally modular.

### P4.1 Generated SDKs & Developer Surface

**Current truth:** a hand-written Python SDK exists, but the generated, scalable developer platform layer does not.

**Work:**

- Generate formal API schema(s) where missing.
- Ship generated SDKs for Python and TypeScript first.
- Add examples, auth flows, pagination, retries, and compatibility guarantees.

**Acceptance:**

- Developers can install supported SDKs with current API coverage and reference docs.

### P4.2 Developer Portal

**Work:**

- Provide interactive documentation, changelog, onboarding, and plugin development guidance.
- Connect SDK docs, API reference, and plugin patterns in one place.

**Acceptance:**

- External developers can discover, test, and build integrations without reading the source tree first.

### P4.3 Marketplace MVP

**Current truth:** plugin architecture is strong, but there is no third-party distribution or monetization surface.

**Work:**

- Add marketplace registry and install metadata.
- Start with free/community plugin distribution if paid flows are too large for MVP.
- Support compatibility/versioning rules and plugin trust metadata.

**Acceptance:**

- A plugin can be published, discovered, and installed through a marketplace flow.

### P4 Success

- Morpheus gains the beginning of an ecosystem moat instead of shipping only first-party depth.

---

## Phase P5 — Collaboration & Workflow

**Goal:** make Morpheus workable for real teams, not just single operators.

### P5.1 Visual Workflow Builder

**Current truth:** rule/workflow infrastructure exists, but there is no merchant-grade visual builder.

**Work:**

- Build a visual trigger-condition-action editor on top of hooks/events.
- Reuse existing event surfaces rather than inventing a second event system.
- Add execution history, retries, and status visibility.

**Acceptance:**

- Merchant can create and activate a workflow without code.

### P5.2 Content Approval & Staging

**Work:**

- Add approval states, review flow, staging/preview, and scheduled publish.
- Use existing approval/audit patterns where they already exist in other subsystems.

**Acceptance:**

- Content changes can be reviewed and scheduled before going live.

### P5.3 Team Coordination Surfaces

**Work:**

- Add assignee/reviewer concepts where needed for workflows and AI-generated content.
- Ensure notifications and activity feeds reflect collaborative work, not only system events.

**Acceptance:**

- Teams can coordinate review/approval work without leaving the platform.

### P5 Success

- Morpheus supports multi-role merchant teams with traceable approval flows.

---

## Phase P6 — Advanced Optimization

**Goal:** ship higher-complexity differentiators after the foundation is trustworthy.

### P6.1 Dynamic Pricing Engine

- Build guardrailed pricing automation around margins, inventory, seasonality, and demand.
- Keep B2B/static pricing and dynamic pricing clearly separated in ownership and precedence.

### P6.2 AI Fraud Scoring

- Evolve from static fraud rules to risk scoring with review thresholds and operator visibility.

### P6.3 Peer Benchmarking Rollout

- Launch privacy-safe cohort benchmarking once P2 architecture and data policy are ready.

### P6.4 Live Commerce

- Explore as a later-channel expansion, not as a foundation-phase distraction.

### P6 Success

- Morpheus adds differentiated optimization features without compromising trust or clarity.

---

## Recommended Shipping Order

If the goal is maximum ROI with realistic sequencing, ship in this order:

1. **P3.1 RBAC enforcement**
2. **P1.2 Unified AI Content Suite**
3. **P1.1 Linda Copilot Upgrade**
4. **P2.1 Report Builder MVP**
5. **P3.2 PII encryption**
6. **P3.3 Immutable audit**
7. **P2.3 Search Analytics Dashboard**
8. **P4.1 Generated SDKs**
9. **P4.3 Marketplace MVP**
10. **P5.1 Visual Workflow Builder**

That order balances visible merchant value with the enterprise trust work that cannot be deferred forever.

---

## Backlog Classification

| Capability | Plan state | Primary phase |
|---|---|---|
| Linda approval-gated copilot | `missing_core_gap` | P1 |
| Unified AI content suite | `missing_core_gap` | P1 |
| Visual merchandising workbench | `missing_core_gap` | P1 |
| Custom report builder | `missing_core_gap` | P2 |
| Scheduled reports | `missing_core_gap` | P2 |
| Reporting/invoice PDF coverage | `missing_core_gap` | P2 |
| Search analytics dashboard | `missing_core_gap` | P2 |
| Peer benchmarking | `later_differentiator` | P2/P6 |
| RBAC enforcement | `missing_core_gap` | P3 |
| PII encryption | `missing_core_gap` | P3 |
| Immutable audit | `missing_core_gap` | P3 |
| SCIM provisioning | `missing_core_gap` | P3 |
| SOC 2 readiness | `missing_core_gap` | P3 |
| Generated SDKs | `missing_core_gap` | P4 |
| Developer portal | `missing_core_gap` | P4 |
| Marketplace MVP | `missing_core_gap` | P4 |
| Visual workflow builder | `missing_core_gap` | P5 |
| Content approvals/staging | `missing_core_gap` | P5 |
| Dynamic pricing | `later_differentiator` | P6 |
| AI fraud scoring | `later_differentiator` | P6 |
| Live commerce | `later_differentiator` | P6 |

---

## Out of Scope For This Plan

These items may matter, but they are not part of this specific execution sequence:

- Re-auditing the entire enterprise report from scratch
- Replacing already-working AI/admin surfaces with brand-new duplicate systems
- A full multi-tenant organization model rollout
- B2B depth work beyond the trust/platform layers already captured in companion reports
- Theme redesign work unrelated to the capability gaps in this plan

---

## Exit Criteria

This plan is successful when all of the following are true:

- Morpheus can demonstrate a coherent AI-native merchant workflow story in-product.
- Enterprise reviewers no longer hit immediate red flags on authorization, audit, identity, or PII handling.
- Developers can integrate and extend Morpheus through supported SDK and marketplace paths.
- Merchant teams can collaborate through built-in workflow and approval surfaces.
- The platform's strongest differentiators are visible at the product layer, not only buried in architecture.

---

# Engineering Review (2026-08-11)

Claims below were checked against the tree, not taken from the source report.
Where the plan's "current truth" disagrees with the code, the code wins.

## The load-bearing factual error

> *"A Python SDK exists. The real gap is generated SDKs…"* (Corrected Baseline)

What exists is `morpheus/` — the **plugin-authoring** SDK (`morpheus.{app,theme,core}`,
shipped v0.33/v0.34). There is **no HTTP API client SDK**: no `MorpheusClient`, no
requests/httpx client anywhere in the tree. There is also no OpenAPI schema
(no drf-spectacular in `requirements.txt`).

Those are different products for different audiences. **P4.1 is mis-sized** — it is
scoped as "generate SDKs where a hand-written one exists", but there is nothing to
generate *from*. Its real first step (produce an API schema) is not in the plan.

## Where the plan overstates the gap

| Plan says | Ships today |
|---|---|
| P1.1 "add approval-gated action plans" | `OpsProposal` staging, `AgentApprovalRequest`, `core/assistant/consent.py` (kernel-verified human consent), the scope→budget→deadline→approval chain, AI-Act evidence export (v0.31), merchant guardrails (v0.32) |
| P1.2 "add batch processing" | `ai_content/services_bulk_catalog.py` |
| P2.3 search analytics | `SEARCH_PERFORMED` already fires server-side (`storefront/views/catalog.py:221`) into `core/self_improvement/collectors/zero_search.py` |
| P5.1 "no visual builder" | `workflows` has `engine.py`, an editor, `runs.html`, and a test harness |
| P6.1 dynamic pricing (phased last) | The `PRODUCT_CALCULATE_PRICE` seam shipped v0.38 on **both** display and charge paths |

The consent kernel is arguably *ahead* of what P1.1 asks for. **P6.1 is mis-phased**:
the hard part (a price seam that cannot diverge between quoted and charged) is done,
so a merchant pricing-rules UI is far cheaper than "P6 advanced" implies. Promote it.

## Where the plan is right, and it matters

**P3.1 RBAC is the real finding.** `has_capability()` exists in `rbac/services.py` and
exactly **3 files** in the repo call it. Any `is_staff=True` user can do anything.
That is a live authorization hole, not an enterprise checkbox.

Also genuinely absent, as claimed: PII encryption (zero `encrypt` references in `core/`
or `customers/`), SCIM (zero references), invoice/report PDF (reportlab is pinned but
used only by a Gutenberg converter and a cover backfill).

`core/audit/models.py:12` opens with *"One immutable audit row"* — with no hash chain
and no DB-level append-only. Immutable by convention only.

## Cut these

- **P2.4 Peer Benchmarking Foundation** — "design the architecture even if rollout comes
  later" is speculative work with no consumer: the settings-field-with-no-consumer
  landmine promoted to a phase. Also needs cross-merchant data a single-store
  deployment does not have, plus a GDPR legal basis.
- **P3.5 SOC 2 readiness** — ~80% organizational (policies, vendor management, access
  reviews, an auditor, a 3–12 month observation window), $20–60k/yr. In an engineering
  plan it yields a checklist document, not readiness. Keep the technical controls
  (P3.1–3.3); drop the certification track.
- **P4.2 Developer Portal + P4.3 Marketplace at their current position** — the
  sequencing error with real consequences. There is no license boundary and **no CLA**.
  A marketplace *is* external contribution; accepting third-party code without a CLA is
  very hard to unwind. Must follow the open-core edition boundary, not precede it.
- **P1.3 visual merchandising workbench** and **P5.1 node-graph workflow builder** —
  multi-week frontend builds on a dashboard running Tailwind Play CDN with no build step
  (and existing `unsafe-eval` CSP debt for it). `dynamics` already reranks; `workflows`
  already has a working form editor. Polish sold as capability. Defer.

## Structural problems

1. **The plan contradicts itself on ordering.** The phase table runs P1 (AI) → P3
   (trust); "Recommended Shipping Order" puts P3.1 first. Pick one.
2. **18 of 21 backlog items are `missing_core_gap`.** Labelling almost everything a core
   gap is not prioritization. No cost estimates, no inter-phase dependencies.
3. It never references the **open-core plan**, which determines whether any of this is
   free or paid — and it schedules six phases on top of unrepaid debt
   (`/account/payment-methods/` calls live Stripe with its plugin disabled;
   order-dependent test failures; a parallel test runner that cannot report failures).

## Recommended order

1. **RBAC enforcement** — log-only first, then fail closed. Getting this wrong locks
   merchants out of their own store.
2. **Immutable audit** — hash chain + DB trigger; small, and it makes the docstring true.
3. **Search analytics dashboard** — cheap, the data already flows.
4. **Dynamic pricing rules UI** — promoted from P6; the seam exists.
5. **PII encryption** — real; needs care on searchable fields.
6. **OpenAPI schema** — the actual prerequisite for anything called an SDK.

Everything else waits for the edition boundary and the CLA.
