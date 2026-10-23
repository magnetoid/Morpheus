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

# plugins/installed/newsletter/tasks.py

Symbols in `plugins/installed/newsletter/tasks.py`.

- L37 `_unsubscribe_headers(token: str)` (function) — The RFC 8058 one-click pair for one recipient's unsubscribe token.
- L47 `_base_bodies(campaign)` (function) — The campaign's text/html bodies, constant across recipients. Computed
- L55 `_with_footer(base_text: str, base_html: str | None, token: str)` (function) — Append this recipient's one-click unsubscribe footer to the base bodies.
- L70 `send_campaign(self, campaign_id: str)` (function) — Start sending a campaign to every confirmed subscriber. Idempotent.
- L113 `send_campaign_continue(self, campaign_id: str)` (function) — Resume a mid-send campaign's next batch (re-enqueued by the batch loop).
- L118 `_run_campaign_batch(campaign_id: str)` (function) — Send up to ``CAMPAIGN_BATCH_SIZE`` not-yet-sent recipients of a 'sending'
- L223 `send_campaign_test(self, campaign_id: str, to: str)` (function) — Send one test copy to ``to`` — no status change, no audience touch.
- L248 `send_winback(customer)` (function) — Win-back email to a newly at-risk customer — consent-gated, deduped.
