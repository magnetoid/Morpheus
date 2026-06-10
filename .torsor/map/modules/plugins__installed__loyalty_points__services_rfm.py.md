---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-09T21:57:02'
updated: '2026-06-09T21:57:02'
---

# plugins/installed/loyalty_points/services_rfm.py

Symbols in `plugins/installed/loyalty_points/services_rfm.py`.

- L32 `compute_all()` (function) — Nightly task: compute R/F/M for every customer with at least one
- L90 `segment_for_customer(customer)` (function) — Read-only — return the cached segment or None if uncomputed.
- L101 `_quintile_scores(pairs: list[tuple], *, ascending: bool)` (function) — Bucket the (customer_id, value) pairs into quintiles 1-5.
- L120 `_segment_for(r: int, f: int, m: int)` (function) — Map (R, F, M) ∈ [1,5]³ → one of the seven named segments.
- L135 `is_new_customer(customer)` (function) — Recent signup with too little history to RFM-score sensibly.
