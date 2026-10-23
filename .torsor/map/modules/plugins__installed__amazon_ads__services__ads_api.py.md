---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:50'
updated: '2026-10-23T04:51:50'
rules: []
---

# plugins/installed/amazon_ads/services/ads_api.py

Symbols in `plugins/installed/amazon_ads/services/ads_api.py`.

- L21 `list_campaigns()` (function) — POST /sp/campaigns/list → [{id, name, state, budget}].
- L50 `set_campaign_status(campaign_id: str, state: str)` (function) — PUT /sp/campaigns — state in {'ENABLED','PAUSED'}.
- L67 `set_campaign_budget(campaign_id: str, daily_budget: float)` (function) — PUT /sp/campaigns — update an existing campaign's daily budget.
- L95 `create_campaign(*, name: str, daily_budget: float)` (function) — POST /sp/campaigns — a PAUSED auto-targeted Sponsored Products campaign.
