---
type: decision
status: accepted
tags:
- adr
links: []
created: '2026-07-02T06:06:06'
updated: '2026-07-02T06:06:06'
rules:
- id: no-gpl-deps-in-core
  pattern: requirements.*\.txt|pyproject\.toml
  message: 'Adding a dependency? Check its license: a GPL/AGPL dep in core forecloses
    the planned permissive open-core split (ADR: distribution/licensing). MIT/BSD/Apache
    are fine; copyleft needs an explicit owner decision.'
- id: no-multitenant-scaffolding
  pattern: tenant_id|TenantModel|row_level_security|RLS
  message: "Morpheus is deliberately single-tenant (one instance per client \u2014\
    \ agency model, ADR: distribution). Don't add tenant-isolation scaffolding; client\
    \ separation happens at the instance level. Fleet provisioning/update tooling\
    \ is the sanctioned alternative."
---

# ADR 0026: Distribution model: single-tenant instances per client (agency model); licensing deferred to publish time (open-core or FSL), with prep starting now

## Context
The owner's intent for Morpheus OS: deploy and operate instances for his clients (agency model, like dotbooks.store today), under a commercial per-client license near-term, and eventually publish it as open core or open source — final license undecided. The enterprise-AI-first plan (docs/plans/enterprise-ai-first-plan-2026-07.md) had left two strategic forks open: multi-tenancy vs one-instance-per-merchant (Phase 6), and platform licensing posture. The agency model resolves the first: each client gets their own instance, so tenant isolation/RLS/per-tenant keys are NOT needed; what is needed is fleet tooling. The repo currently has no LICENSE file (legally all-rights-reserved), the owner is the sole author (relicensing freedom intact), and the plugin architecture's delete/disable litmus tests (ADR 0023) mean a plugin boundary can serve as a clean license boundary later.

## Decision
(1) TENANCY: Morpheus stays single-tenant — one instance per merchant/client. Do not build multi-tenant isolation (tenant model, RLS, per-tenant token scoping). Invest instead in FLEET tooling: fast provisioning of a new client instance and pushing updates across all instances (the existing self-update system pulling from magnetoid/morpheus is the seed). (2) LICENSING: stay proprietary/all-rights-reserved now; license each client via a commercial services agreement. Defer the public-license choice to publish time, keeping BOTH endpoints open: open-core (MIT/Apache-2.0 core + commercial premium plugins — the AI layer and B2B/marketplace are the premium candidates) or fair-code (FSL/BUSL, source-available with a no-competing-SaaS clause, converting to Apache-2.0 after 2 years). Leaning open-core with MIT core if forced today. (3) PREP NOW regardless of the eventual choice: dependency license audit (no GPL dep may land in core — fold into the SBOM work), keep premium-candidate plugins cleanly separable per ADR 0023, require a CLA from the first external contributor to preserve relicensing freedom, check/secure the "Morpheus OS" trademark, and use a per-client license template that grants no rights constraining the future model.

## Consequences
Phase 6 of the enterprise plan simplifies: multi-tenancy is descoped; fleet provisioning + fleet update automation take its place (much cheaper). A GPL-licensed dependency in core/ becomes an architectural violation, not just a legal footnote. Premium-candidate plugins must keep passing the delete-test so they can move to a commercial repo later. Client contracts must be written knowing the code may later be public. Revisit and supersede this ADR with the concrete license at publish time.
