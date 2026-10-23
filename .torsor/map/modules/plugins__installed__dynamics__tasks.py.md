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

# plugins/installed/dynamics/tasks.py

Symbols in `plugins/installed/dynamics/tasks.py`.

- L24 `recompute_probabilities()` (function) — Full recompute of every active product's purchase probability (nightly).
- L34 `refresh_probabilities_throttled()` (function) — Event-driven refresh (fired after an order). Debounced via a short cache
- L46 `rebuild_bandit_posteriors(window_days: int=30)` (function) — Nightly rebuild of the autopilot bandit's per-segment posteriors from
- L57 `generate_merchandising_proposals()` (function) — Nightly AI merchandiser — file merchandising proposals into the review
