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

# plugins/installed/newsletter/dashboard.py

Symbols in `plugins/installed/newsletter/dashboard.py`.

- L21 `subscribers_view(request)` (function)
- L57 `popups_view(request)` (function)
- L89 `popup_edit_view(request, popup_id: str)` (function)
- L133 `campaigns_view(request)` (function) — Send surface for marketing's EmailCampaigns (Phase 3).
- L155 `campaign_send_view(request, campaign_id: str)` (function) — POST — queue a full send of one campaign to all confirmed subscribers.
- L173 `campaign_test_view(request, campaign_id: str)` (function) — POST — send one test copy to the given (or the staff member's) address.
