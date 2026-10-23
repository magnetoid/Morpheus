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

# plugins/installed/google_shopping/services/ads_api.py

Symbols in `plugins/installed/google_shopping/services/ads_api.py`.

- L30 `ads_config()` (function)
- L39 `ads_connected()` (function)
- L44 `_headers()` (function)
- L55 `_search(query: str)` (function) — Run a GAQL query via searchStream → (rows, error).
- L80 `campaign_report(*, days: int=30)` (function) — Campaign metrics for the last N days.
- L140 `_mutate(resource: str, operations: list[dict])` (function)
- L159 `set_campaign_status(campaign_id: str, status: str)` (function) — Pause/enable a campaign. status in {'ENABLED','PAUSED'}.
- L174 `set_campaign_budget(budget_id: str, daily_amount: float)` (function) — Set a campaign budget's daily amount (in account currency units).
- L187 `create_shopping_campaign(*, name: str, daily_budget: float, merchant_id: str, country: str='US')` (function) — Create a (paused) Standard Shopping campaign tied to the Merchant feed.
