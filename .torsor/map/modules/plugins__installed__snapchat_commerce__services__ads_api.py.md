---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:52'
updated: '2026-10-23T04:51:52'
rules: []
---

# plugins/installed/snapchat_commerce/services/ads_api.py

Symbols in `plugins/installed/snapchat_commerce/services/ads_api.py`.

- L16 `_acct()` (function)
- L20 `list_campaigns()` (function)
- L40 `set_campaign_status(campaign_id: str, status: str)` (function) — status in {'ACTIVE','PAUSED'}.
- L56 `create_campaign(*, name: str, daily_budget: float)` (function) — Create a PAUSED campaign (objective on Snap = budgets live on ad squads,
- L71 `campaign_report(*, days: int=30)` (function) — Account stats broken down by campaign (spend, impressions, swipes,
- L126 `_iter_stat_rows(data)` (function) — Snap nests stats under total_stats[].total_stat.breakdown_stats.campaign[]
- L140 `_f(v)` (function)
