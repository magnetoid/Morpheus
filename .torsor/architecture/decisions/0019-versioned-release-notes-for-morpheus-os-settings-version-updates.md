---
type: decision
status: accepted
tags:
- adr
links: []
created: '2026-06-20T22:50:48'
updated: '2026-06-20T22:50:48'
rules:
- id: release-notes-on-version-bump
  description: "Any change to MORPHEUS_VERSION must add a matching `## vX.Y.Z \u2014\
    \ YYYY-MM-DD` entry to docs/RELEASE_NOTES.md in the same change."
  applies_to:
  - morph/settings.py
  - docs/RELEASE_NOTES.md
  severity: error
- id: release-notes-is-source-of-truth
  description: "The in-dashboard Settings \u2192 Version & updates page renders docs/RELEASE_NOTES.md;\
    \ never hardcode changelog content in the release_notes plugin or templates."
  applies_to:
  - plugins/installed/release_notes
  severity: warn
---

# ADR 0019: Versioned release notes for Morpheus OS (Settings → Version & updates)

## Context
Operators/merchants need a user-facing changelog inside the dashboard, not just the dev-level PR history in CHANGELOG.md. The running version was only an env var (MORPHEUS_VERSION) with no surfaced history of what each version changed in the OS core. Without a hard rule, version bumps ship without a corresponding human-readable note and the in-dashboard changelog silently rots.

## Decision
docs/RELEASE_NOTES.md is the single source of truth for the in-dashboard Morpheus OS changelog. EVERY Morpheus OS version bump (any change to MORPHEUS_VERSION) MUST, in the same change, add a dated, versioned heading `## vX.Y.Z — YYYY-MM-DD` to docs/RELEASE_NOTES.md describing the core update in user-facing terms (newest entry first). The release_notes plugin renders this document at Dashboard → Settings → Version & updates (/dashboard/apps/release_notes/version/), alongside the live MORPHEUS_VERSION. The plugin owns no data — it only displays the doc. Deep engineering/PR-level history stays in CHANGELOG.md; RELEASE_NOTES.md is the curated, operator-facing core changelog.

## Consequences
Version bumps are coupled to a release-note entry (a bump without a matching docs/RELEASE_NOTES.md heading is a rule violation). The Settings page always reflects the current document. New OS-core features must be summarized for a non-engineer audience. Two changelogs are maintained on purpose: RELEASE_NOTES.md (curated, in-dashboard) and CHANGELOG.md (dev/PR-level).
