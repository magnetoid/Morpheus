---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-10T20:08:50'
updated: '2026-06-10T20:08:50'
---

# plugins/installed/experiments/services.py

Symbols in `plugins/installed/experiments/services.py`.

- L38 `visitor_id_for(request)` (function) — Stable cookie/session-backed id. Sets the cookie if missing
- L53 `variant_for(request, experiment_key: str)` (function) — Return the variant name. Records assignment + exposure lazily.
- L82 `record_conversion(*, experiment_key: str, visitor_id: str, revenue: Decimal | None=None)` (function) — Bump conversions + revenue for the visitor's assigned variant.
- L118 `results_for(experiment)` (function) — Aggregate experiment results with lift + z-score per variant
- L187 `_control_or_empty(experiment_key: str)` (function) — Return the control variant if the experiment exists in draft/paused/
- L198 `_bump_exposure(experiment, variant: str)` (function)
- L209 `_bump_conversion(experiment, variant: str, revenue: Decimal | None)` (function)
- L221 `_rate(num, denom)` (function)
- L225 `__sum(field)` (function)
