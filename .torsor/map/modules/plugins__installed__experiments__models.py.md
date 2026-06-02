---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-02T18:07:52'
updated: '2026-06-02T18:07:52'
---

# plugins/installed/experiments/models.py

Symbols in `plugins/installed/experiments/models.py`.

- L36 `Experiment` (class) — One A/B test definition.
- L58 `__str__(self)` (method)
- L62 `variant_names(self)` (method)
- L65 `pick_variant(self, visitor_id: str)` (method) — Deterministic assignment from a stable visitor id (cookie/session).
- L85 `Assignment` (class) — Recorded variant per visitor — lazy-written on first exposure.
- L104 `__str__(self)` (method)
- L108 `Exposure` (class) — Append-only roll-up of exposures + conversions, daily granularity.
- L131 `__str__(self)` (method)
