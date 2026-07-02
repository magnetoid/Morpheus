# Enterprise AI-first commerce OS — the gap plan

> 2026-07-02. Merges (a) the 14-dimension enterprise audit
> (`enterprise-readiness-2026-07.md`, scored 6/10) minus what has since shipped,
> and (b) a fresh evidence-grounded map of the AI/agent layer vs the charter's
> "AI-first enterprise OS" claim. This is the working roadmap; tick items off here.

## Where we actually are

**Engineering:** strong architecture (hook kernel, boundary ratchet, disable
gating, breakers, payment idempotency) but weak operational hardening.
**AI layer:** far more real than a bolt-on — 159 agent tools, 10 LLM providers
behind a circuit breaker + fallback chain + Redis output cache, per-run
cost/latency observability, a 4-audience MCP cluster, UCP/agent.json discovery
manifests, agentic checkout Phase 1 (read/quote), a safety boundary at plan
stage, consensus review, memory tiers. **Verdict: the kernel is ~80% of the
charter; the "enterprise" claim currently fails on governance (audit/approval
at the edge), compliance (PII), deploy safety, and scale (rate limits, tenancy).**

Shipped since the audit (don't redo): outbox drain scheduled + bounded retry +
NATS guard (v0.2.20); `check --deploy` enforcing; mypy baseline in CI; error
capture+reads consolidated into core/errors, boundary 24→22 (v0.2.21, ADR 0025).

---

## Phase 0 — Finish the quick wins (days, all S)
Close the audit items that are one-liners or near:
- [ ] Flip `pip-audit` to enforcing (`continue-on-error: false` after one-time triage) — ci.yml:56.
- [ ] Populate the lockfile (`uv.lock` is 52 bytes — effectively empty); commit it; CI installs from it.
- [ ] Wire the **20 orphaned pytest-style plugin test suites** into CI (module-level `def test_` in `tests/__init__.py` — Django's runner reports "Ran 0 tests"). Convert to `TestCase` or add pytest to CI. **Plus a CI guard** that fails on new module-level test functions — the count grew 19→20 during this work, so it's an active regression class, not one-time debt.
- [ ] Webhook delivery idempotency: dedup key on `deliver_webhook` so broker redelivery can't double-POST (double-charge/double-email class).
- [ ] Ship v0.2.22 (hero animation — committed, unpushed).

## Phase 1 — Agent-write governance (the AI-first enterprise core; ~1-2 wks)
An enterprise buyer's first question is "what stops the AI from doing damage,
and can I see everything it did?" Today: partially, and no.
- [ ] **Enforce `requires_approval` at the MCP layer.** 16 admin tools declare it; the MCP dispatch wires no `approval_check` callback, so Bearer tokens get the full write catalog. Add the approval middleware to `/mcp/admin/v1/` (+ GraphQL agent endpoint), with a pending-approval queue surfaced in the dashboard.
- [ ] **AI audit trail (core).** No record exists of which agent proposed/executed which change when. Log every TOOL_CALLING event (agent identity, tool, args-hash, outcome, approval state) to an append-only core model; surface in Settings → Developer. This is also the input for rollback.
- [ ] **Rate limiting on MCP + GraphQL** — token-bucket per Bearer token (+IP), burst caps; an external agent must not be able to exhaust the catalog or DOS write tools.
- [ ] **Verify agent order-attribution end-to-end** — `X-Verified-Agent-*` middleware exists but the Order stamping wasn't found in code; make `Order.metadata.agent_id` provable with a test.

## Phase 2 — Compliance & money correctness (~2 wks)
- [ ] **Encrypt PII at rest**: `smtp_password` (core/models.py plaintext), order email/ip/user_agent, plugin API keys in `PluginConfig.config`. Field-level encryption + config-change audit trail. (GDPR Art. 32 exposure on any DB dump.)
- [ ] **Fix partial-failure GDPR anonymization** (customers/services.py) — a failed step must abort, not mark the account anonymized with PII remaining.
- [ ] **Classify refund exceptions** (stripe_gateway.py bare `except`) — transient (network/5xx → retry) vs permanent (card/4xx → surface); stop stranding refunds.
- [ ] **Stripe vault ops behind a circuit breaker** (create_setup_intent, list_payment_methods burn 20s timeouts per call during a Stripe outage).

## Phase 3 — Deploy pipeline (**PARKED by owner, 2026-07-02**)
Owner call: not important right now — acceptable risk for the current
single-operator stage. Revisit when client instances go live (an outage then
hits customers, not just dotbooks.store). Original scope kept below for that
revisit. Push-to-main = live prod deploy, no staging, no smoke, no rollback.
Two 503 outages already (PR #62/#64). Needs owner decisions, not just code:
- [ ] Staging: a `staging` branch + second Coolify app (cheapest path), promote to main on green.
- [ ] Post-deploy smoke: Coolify healthcheck → curl /healthz + a checkout-path probe; auto-rollback to previous image on failure.
- [ ] Branch protection: require CI green on main (GitHub setting — `needs:` can't cross workflows).
- [ ] Migration rollback runbook + tested backup-restore path (core/updates.py reverts code, not schema).

## Phase 4 — Quality ratchet (ongoing, start now)
- [ ] Coverage floor 40% → 60% (per-package minimums: core 85%, payments/orders/catalog 80%).
- [ ] mypy: baseline → enforcing on core/, then payments/orders.
- [ ] Permission-boundary test matrix per staff view (use the `permission-boundary-tests` skill).
- [ ] Plugin-to-plugin import gate (parallel to check_core_boundary.py) for the 430+ undeclared cross-plugin imports; declare `optional_requires`.
- [ ] bookvault → PRODUCT_FORM_CARDS + new PRODUCT_LIST_COLUMNS hook (last known ADR-0023 leak).
- [ ] storefront account sub-pages → contributed ACCOUNT_PAGES hook (ADR 0013 debt).
- [ ] Error-logging Phase C: data-migrate + drop the observability plugin's parallel ErrorEvent table.

## Phase 5 — AI capability leap (differentiators; ~1 mo, parallelizable)
- [ ] **Embeddings + pgvector**: semantic product search on the storefront AND semantic recall for agent memory (`MemoryItem` is exact-key only today). One embedding pipeline serves both.
- [ ] **Evals harness**: prompt/agent regression suite — golden tasks per tool, success-rate tracking per prompt version; wire self-improvement signals back into prompt quality. Without evals, every prompt tweak is an untested prod deploy.
- [ ] **Agentic checkout Phase 2**: the money path (`completeCheckoutSession` is a stub) — Stripe Shared Payment Token redemption, behind the existing `acp.checkout` scope + approval gate from Phase 1.
- [ ] **LLM cost budgets**: per-day/agent spend caps with alerting (observability already tracks cost; add the limiter).
- [ ] AI-native merchandising: upgrade personalisation from co-purchase stats to embedding-based similarity (reuses the pgvector work).

## Phase 6 — Scale & platform posture (**tenancy fork RESOLVED — ADR 0026**)
**Decision (2026-07-02):** Morpheus stays **single-tenant — one instance per
client** (agency model). Multi-tenancy (tenant model, RLS, per-tenant keys) is
**descoped**. Licensing: proprietary now, per-client commercial agreements;
public license (open-core MIT vs FSL) decided at publish time.
- [ ] **Fleet tooling** (replaces multi-tenancy): provision a new client
      instance fast (scripted Coolify app + env + domain), and push updates
      across all instances — extend the existing self-update system
      (pull-from-`magnetoid/morpheus`) into a fleet channel with per-client
      version pinning + staged rollout.
- [ ] **License prep** (keeps open-core AND FSL endpoints open):
      dependency license audit — no GPL/AGPL dep in core (drift rule added);
      keep premium-candidate plugins (AI layer, B2B, marketplace) cleanly
      separable per ADR 0023; CLA required from the first external contributor;
      trademark check on "Morpheus OS"; per-client license template that grants
      no rights constraining the future model.
- [ ] Publish OpenAPI 3.1 for /v1/* + GraphQL schema endpoint (external integrators currently reverse-engineer).
- [ ] SBOM + trivy image scan + scheduled CVE rescans in cd.yml (doubles as the license-audit input).
- [ ] Split the 696-LOC catalog Product god-object into OneToOne plugin extensions (per ADR 0006).

## Sequencing logic
Phase 0 now (days). Phases 1+2 next in parallel — governance is the AI-first
blocker, compliance is the legal one. Phase 3 needs your ops decisions (staging
app, branch protection) — schedule a session for it. Phase 4 runs as a standing
ratchet alongside everything. Phase 5 starts once 1 is done (approval gates must
precede an agentic money path). Phase 6's tenancy fork is resolved (ADR 0026:
single-tenant + fleet tooling); its remaining items can start anytime — fleet
provisioning in particular compounds with every new client onboarded.
