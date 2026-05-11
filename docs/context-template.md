# Session Context & Handoff

> Update this at the end of every session. Feed this file (and *only* this file) into the next session to instantly restore context. Pillar 2 of [universal-principles.md](universal-principles.md). Phase 6 of [workflow-guide.md](workflow-guide.md).

## Current Date: `[YYYY-MM-DD]`

## 1. What Was Completed Last Session?

- [e.g., Set up the PostgreSQL database schema]
- [e.g., Implemented the authentication flow using NextAuth]
- [e.g., Built the `UserProfile` component]

Link each item to its commit / PR if possible: `feat(auth): add NextAuth flow (#42)`.

## 2. Current Project State & Architecture

- **Key files modified:** `src/auth.ts`, `src/components/UserProfile.tsx`
- **Branch:** `feature/<name>`
- **Tests passing:** yes / no — and which suite

## 3. Decisions Log

*(Decisions made during the session that aren't visible in the code — rejected approaches, trade-offs, things you considered and skipped. This is what stops the next session from re-litigating settled questions.)*

- **Decision:** Chose JWT strategy instead of database sessions.
  - **Reason:** Read-heavy workload; DB sessions added 30ms median latency in our load test.
  - **Rejected:** Hybrid approach — too much complexity for the throughput we have.
- **Decision:** ...

## 4. Open Issues / Known Bugs

- [e.g., The login modal animation stutters on mobile]
- [e.g., Need to validate the Stripe webhook payload]

## 5. Next Steps (Action Items, Prioritized)

1. [ ] Fix the login modal animation. *(Why: Pillar 4 — bug spotted in last verify pass.)*
2. [ ] Build the webhook endpoint in `app/api/webhooks/route.ts`. *(Why: spec section 4, feature 2.)*
3. [ ] Write unit tests for the webhook logic. *(Why: Pillar 5 — TDD.)*

## 6. Spec Drift?

*(Did anything change in the implementation that should be reflected back in `spec-template.md`? Update both, or note it here for the next session to reconcile.)*

- ...

---

**Agent prompt for next session:** *"Read this context file. Confirm you have read it. Acknowledge the 'Next Steps' and ask me which one we should tackle first. Do not write code yet."*
