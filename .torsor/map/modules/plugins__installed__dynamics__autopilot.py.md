---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:51'
updated: '2026-10-23T04:51:51'
rules: []
---

# plugins/installed/dynamics/autopilot.py

Symbols in `plugins/installed/dynamics/autopilot.py`.

- L36 `ensure_default_blocks(*, slots=None)` (function) — Idempotently provision an enabled ``autopilot`` block on each slot that has
- L60 `generate_proposals()` (function) — Inspect the store's signals and file merchandising proposals (propose-only,
- L72 `_auto_apply_enabled()` (function) — The merchant's 'skip the review queue for low-risk actions' toggle
- L83 `_auto_apply_actionables()` (function) — Auto-approve the just-filed low-risk (actionable) proposals when the
- L97 `_autopilot_draft()` (function)
- L116 `_feature_drafts()` (function) — Propose featuring the highest-propensity products that aren't featured yet.
- L149 `_enrich_with_llm(drafts: list[dict])` (function) — If an AI provider is configured, rewrite the drafts' titles/rationales in
- L193 `_persist(drafts: list[dict])` (function) — Create a row per draft unless an OPEN (proposed) one with the same
- L220 `apply_proposal(proposal, *, actor=None)` (function) — Apply an approved proposal's config action (low-risk only) and audit it.
- L252 `_apply_feature(payload)` (function)
- L261 `_apply_provision(payload)` (function)
- L268 `dismiss_proposal(proposal, *, actor=None)` (function)
