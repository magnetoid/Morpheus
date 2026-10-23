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

# plugins/installed/microsoft_commerce/services/ads_api.py

Symbols in `plugins/installed/microsoft_commerce/services/ads_api.py`.

- L24 `list_campaigns()` (function) — GetCampaignsByAccountId → [{id, name, status, budget}]. No metrics.
- L52 `campaign_report(*, days: int=30)` (function)
- L59 `set_campaign_status(campaign_id: str, status: str)` (function) — UpdateCampaigns Status. status in {'Active','Paused'}.
- L78 `create_campaign(*, name: str, daily_budget: float)` (function) — AddCampaigns — a PAUSED Shopping campaign (daily budget in account currency).
