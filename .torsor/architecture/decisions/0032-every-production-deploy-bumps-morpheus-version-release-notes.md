---
type: decision
status: accepted
tags:
- adr
links: []
created: '2026-07-08T02:13:01'
updated: '2026-07-08T02:13:01'
rules:
- id: deploy-version-bump
  severity: error
  applies_to: any push/merge to main (Coolify auto-deploys)
  rule: "A production deploy MUST bump MORPHEUS_VERSION (vMAJOR.MINOR.PATCH; PATCH=fix/polish,\
    \ MINOR=feature, MAJOR=breaking) AND add a matching dated '## vX.Y.Z \u2014 YYYY-MM-DD'\
    \ entry to docs/RELEASE_NOTES.md describing the change."
  rationale: "merge-to-main auto-deploys; Settings \u2192 Version & updates reads\
    \ MORPHEUS_VERSION + RELEASE_NOTES.md, so an unversioned deploy ships changes\
    \ users cannot see in the changelog and drifts the reported version behind production."
---

# ADR 0032: Every production deploy bumps MORPHEUS_VERSION + release notes

## Context
Merging/pushing to `main` is itself a production deploy — Coolify watches the repo and builds+deploys dotbooks.store on every push (CLAUDE.md landmine). The dashboard's **Settings → Version & updates** page (the `release_notes` plugin) renders the running `MORPHEUS_VERSION` (morph/settings.py:39, `config('MORPHEUS_VERSION', default=...)`) alongside `docs/RELEASE_NOTES.md`, which is the single source of truth for the in-dashboard changelog.

The prior "Versioned release notes" ADR only required a notes entry when the version was *bumped*. But deploys can — and do — ship without a bump: the 2026-07-08 dashboard UI/UX polish (breadcrumb dedup, dark-mode fixes, micro-animations; commits 42e71071/366839a6/e2fe3e61) merged to main and went live while the dashboard still reported v0.2.27 with no changelog entry. Result: what's running in production silently drifts ahead of the version + changelog users can see, defeating the whole point of the Version & updates surface.

## Decision
Every push/merge to `main` (= a production deploy) MUST, in the same batch:

1. **Bump `MORPHEUS_VERSION`** using `vMAJOR.MINOR.PATCH` — PATCH for fixes/polish/refactors, MINOR for user-facing features, MAJOR for breaking changes. The default lives in `morph/settings.py`; if a deploy env pins `MORPHEUS_VERSION`, update it there too.
2. **Add a dated `## vX.Y.Z — YYYY-MM-DD` entry** (newest first) to `docs/RELEASE_NOTES.md` explaining the change in user-facing terms — this is what renders at Settings → Version & updates.

Batch several local commits into ONE deploy carrying ONE bump + ONE entry (do not thrash Coolify with rapid successive merges). The version in the dashboard must always equal what is actually running in production.

## Consequences
The in-dashboard changelog always reflects what is live. A main-bound PR/commit that changes behaviour without a version bump + matching RELEASE_NOTES entry is incomplete and can be rejected on review. Small per-deploy overhead, mitigated by batching. Enforcement can later be promoted to a pre-push/CI hook (assert `MORPHEUS_VERSION` changed and its `## v…` entry exists whenever main advances), mirroring the existing `makemigrations --check` gate. Extends, does not replace, the "Versioned release notes" ADR.
