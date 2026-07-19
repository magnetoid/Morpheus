---
type: decision
status: accepted
tags:
- adr
links: []
created: '2026-07-19T02:12:42'
updated: '2026-07-19T02:12:42'
rules:
- id: version-bump-on-app-or-theme-change
  description: A change to app code (core/, plugins/installed/, morph/) or theme code
    (themes/) must bump MORPHEUS_VERSION and add a dated docs/RELEASE_NOTES.md entry
    in the same deploy.
  severity: error
---

# ADR 0033: Any app-code or theme-code change bumps MORPHEUS_VERSION

## Context
CLAUDE.md / ADR 0032 already state that every merge to main is a production deploy and must bump MORPHEUS_VERSION + add a dated RELEASE_NOTES entry. In practice theme-only edits (themes/library/dot_books/**, CSS/template polish) were being treated as "not real code" and shipped without a bump, so Settings → Version & updates silently under-reported what users actually got. This rule makes the trigger explicit and symmetric across both surfaces.

## Decision
A change to application code (core/**, plugins/installed/**, morph/**) OR to theme code (themes/**) is a versioned change: it bumps MORPHEUS_VERSION and adds a matching dated docs/RELEASE_NOTES.md entry in the same deploy. Theme edits are not exempt. Batch local commits into one deploy carrying one bump (PATCH = fix/polish/theme tweak, MINOR = feature, MAJOR = breaking).

## Consequences
No unversioned deploys: every shipped change — including pure theme/CSS/template polish — is legible in the changelog. Redundant-feeling for tiny theme tweaks, but the deploy-smoke /readyz version-convergence gate already assumes a bump per push, so this keeps prod and the release notes in lockstep.
