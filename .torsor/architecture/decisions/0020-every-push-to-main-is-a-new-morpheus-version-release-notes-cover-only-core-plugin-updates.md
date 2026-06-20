---
type: decision
status: accepted
tags:
- adr
links: []
created: '2026-06-20T23:31:13'
updated: '2026-06-20T23:31:13'
rules:
- id: version-bump-every-push
  description: "Each push to main bumps MORPHEUS_VERSION (morph/settings.py) and adds\
    \ a matching ## vX.Y.Z \u2014 YYYY-MM-DD entry to docs/RELEASE_NOTES.md."
  applies_to:
  - morph/settings.py
  - docs/RELEASE_NOTES.md
  severity: error
- id: release-notes-core-and-plugins-only
  description: RELEASE_NOTES.md entries describe ONLY core/** and plugins/installed/**
    behavior changes; exclude docs, tests, CI, formatting, pure refactors, chores.
  applies_to:
  - docs/RELEASE_NOTES.md
  severity: warn
supersedes: 0019-versioned-release-notes-for-morpheus-os-settings-version-updates
---

# ADR 0020: Every push to main is a new Morpheus version; release notes cover only core + plugin updates

## Context
The user wants the in-dashboard changelog (Settings → Version & updates) to advance on every GitHub push to main (each push deploys to prod via Coolify), and to read as a product changelog — describing only what changed in the Morpheus OS *core* and its *plugins*, not noise like docs, tests, CI, formatting, or chores. ADR 0019 established docs/RELEASE_NOTES.md as the source of truth and coupled it to MORPHEUS_VERSION; this refines the cadence and the content filter.

## Decision
Every push to main bumps MORPHEUS_VERSION (semver; default lives in morph/settings.py) and adds a matching `## vX.Y.Z — YYYY-MM-DD` entry to docs/RELEASE_NOTES.md in the SAME push. The entry describes ONLY core (core/**) and plugin (plugins/installed/**) changes that affect behavior or capabilities — written for an operator, newest first. Explicitly EXCLUDE from the notes: docs-only changes, tests, CI/infra, formatting/lint, refactors with no behavior change, and chores. If a push contains only excluded changes, still bump the patch version but the entry may be a single line like "Maintenance: no functional changes." The page renders this doc verbatim (release_notes plugin); never hardcode changelog content.

## Consequences
MORPHEUS_VERSION advances on every deploy, giving a clean operator-facing history. Release notes stay signal-rich (core + plugins only). Authors must classify their change: core/plugin behavior → a note; docs/tests/chore → version bump only. PR-level engineering detail still lives in CHANGELOG.md.
