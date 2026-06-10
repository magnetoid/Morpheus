---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-09T21:57:02'
updated: '2026-06-09T21:57:02'
---

# plugins/installed/loyalty_points/services_tiers.py

Symbols in `plugins/installed/loyalty_points/services_tiers.py`.

- L21 `ensure_default_tiers()` (function) — Idempotently seed the default 3-tier ladder. Returns rows created.
- L41 `assign_tier(customer)` (function) — Compute + persist this customer's tier from their 12-month revenue.
- L70 `assign_all()` (function) — Bulk assignment — for the nightly Celery task. Returns counts.
- L103 `_default_perks_for(key: str)` (function)
