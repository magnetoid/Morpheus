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

# plugins/installed/post_purchase/analytics.py

Symbols in `plugins/installed/post_purchase/analytics.py`.

- L18 `_bucket(score: int)` (function)
- L26 `_nps(promoters: int, detractors: int, total: int)` (function)
- L32 `nps_summary(days: int=90)` (function) — Rolling-window NPS + bucket counts + response rate.
- L56 `nps_trend(weeks: int=12)` (function) — Per-ISO-week NPS, oldest → newest. Empty weeks are omitted.
- L80 `nps_by_product(days: int=90, limit: int=20)` (function) — Per-product NPS. Multi-item orders attribute the response to every item
- L114 `recent_detractors(limit: int=20)` (function) — Detractor responses (score ≤ 6), newest first — comments to read.
