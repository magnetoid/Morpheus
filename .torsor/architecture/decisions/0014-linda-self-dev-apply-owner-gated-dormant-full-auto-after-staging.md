---
type: decision
status: accepted
tags:
- adr
links: []
created: '2026-06-08T13:36:09'
updated: '2026-06-08T13:36:09'
rules:
- id: selfdev-apply-requires-killswitch
  pattern: (def .*apply.*proposal|promote_to_prod|self_update.*apply|code_apply)
  message: Any self-dev APPLY/PROMOTE path must hard-check MORPHEUS_SELF_UPDATE_ENABLED
    (default OFF) AND the selfdev scope AND owner-only approval before touching the
    repo or a deploy. No apply path may run when the switch is unset. (ADR 0014.)
- id: selfdev-blocked-paths
  pattern: selfdev|code_apply|code_draft
  message: 'Self-dev may write ONLY under plugins/installed/. Hard-blocked forever
    (not gateable): core/, morph/settings.py, core/safety.py, themes/, payments/money,
    destructive migrations, secrets/env. Self-dev cannot widen core/safety.py -- it
    reads it. (ADR 0014.)'
- id: selfdev-no-self-approve
  pattern: (consensus|aggregate|evaluate).*(approve|auto_apply|self_approve)
  message: Consensus is ADVISORY, never approval. Linda never self-approves an apply.
    A human owner (superuser) approves at a type-to-confirm ack+echo gate, upfront,
    per proposal. (ADR 0014.)
---

# ADR 0014: Linda self-dev apply: owner-gated, dormant, full-auto-after-staging

## Context
Linda's self-building pipeline (Hermes-grade uplift, docs/plans/linda-self-learning-uplift-2026-06.md) is shipped up to the DRAFT boundary: propose -> sandbox -> static-scan (codegen.scan_source) -> consensus (2/3 quorum) -> CodeProposal(status=draft). It deliberately STOPS before writing to the repo or executing generated code in the live process. The remaining tail -- Phase 4 apply (approved proposal -> live code) and Phase 7 staging->promote (deploy to a staging clone, evaluate, go public) -- was explicitly NOT built pending a signed-off gating policy, because a self-writing agent on a live store is the single highest-blast-radius capability in the platform. The owner (superuser) ratified the four open axes on 2026-06-08. This ADR is that sign-off. Relates to ADR 0011 (one generic agent) and ADR 0010 (tiny core); the self-improvement engine + core/safety.py are core, per CLAUDE.md.

## Decision
NON-NEGOTIABLE DEFAULTS (locked): (1) Master kill switch MORPHEUS_SELF_UPDATE_ENABLED -- env var, default OFF, flippable only by ops at the deploy layer, never by Linda or the dashboard; the entire apply/promote path is inert until set. (2) Hard-blocked targets forever, not even gateable: core/, morph/settings.py, core/safety.py, themes/, payments/money, destructive migrations (column drop / table rename), secrets/env; self-dev READS core/safety.py and can never widen it. (3) Mandatory pre-gate checks -- ALL green or no gate is offered: static scan no CRITICAL/HIGH (codegen.scan_source incl. _shape_findings), security-reviewer clean, consensus quorum 2/3 configured providers (<2 -> insufficient -> defer to human), path allowed by core/safety.py, sandbox tests pass. (4) Linda never self-approves; consensus is advisory only; the human owner approves at a type-to-confirm ack+echo gate. (5) Audit + rollback always: every apply/promote logged to core.audit; rollback (PR close / git revert / staging teardown / skill-disable) always available; reuses core/updates.py backup->migrate->healthcheck->rollback. (6) Circuit breaker: cap self-applies/day; auto-disable the loop on post-apply healthcheck failure or error spike. (7) Linda-only via the selfdev scope; the generic Worker never has it.

FOUR RATIFIED AXES (owner, 2026-06-08): APPLY TARGET = full-auto-after-staging -- once the owner approves a specific proposal and all checks pass, the pipeline carries it through automatically: write -> sandbox -> deploy to STAGING clone (environments plugin) -> eval on staging -> promote to prod ITSELF if staging eval passes; no second human click at promote time. BLAST RADIUS = any plugin file -- self-dev may create new plugins AND edit existing files anywhere under plugins/installed/ (never core/). APPROVER = owner-only -- only a superuser may approve at the gate; no delegation. POSTURE = dormant -- machinery is BUILT but shipped OFF (switch unset); owner flips it on later deliberately.

RESOLVING THE 'NEVER TO MAIN' TENSION: full-auto-after-staging reaches prod without a per-promote human click, narrowing the earlier blanket 'reaching prod always crosses a human step'. Resolution: the human step is the owner's UPFRONT per-proposal approval. Reaching prod still requires, conjunctively: kill switch ON + owner approval of that specific proposal + all mandatory checks green + staging eval pass + circuit breaker not tripped. The promote mechanism (deploy validated branch/snapshot via environments plugin vs merge-to-main) is a build-time detail; either way the gate is upfront approval, not merge-time review, and prod is never reached from an unapproved or check-failing proposal.

## Consequences
Phase 4 apply and Phase 7 staging->promote may now be built, behind the selfdev scope + MORPHEUS_SELF_UPDATE_ENABLED, shipped dormant. The three rules below become advisory drift-guards (promote to PostToolUse hooks if violated in practice, per CLAUDE.md enforcement-layer rule). The environments plugin (Environment/Snapshot/Deployment -- exists, unsurfaced) must be wired for the staging clone + promote step. Build remains gated on this ADR; turning the switch ON is a separate deliberate owner action, not implied by merging the machinery. Supersedes the 'Remaining' caveats in docs/plans/linda-self-learning-uplift-2026-06.md with a ratified policy; that doc now points here.
