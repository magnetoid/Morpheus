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

# plugins/installed/subscriptions/tasks.py

Symbols in `plugins/installed/subscriptions/tasks.py`.

- L51 `_config()` (function) — Read plugin config with sensible defaults if the DB row is absent.
- L69 `_manage_url()` (function) — Absolute URL of the storefront membership page (payment-update / cancel /
- L77 `_has_marketing_consent(customer)` (function) — True only when the customer's most recent consent log opts in to
- L98 `send_dunning_emails(self)` (function) — Send each due, unsent dunning step for every ``past_due`` subscription.
- L127 `_dun_subscription(sub, now, cfg, send_templated_email)` (function) — Send every due+unsent dunning step for one subscription (returns count).
- L186 `_anchor_from_invoice(sub)` (function) — Fallback dunning anchor: the latest open invoice's ``created_at`` (or ``None``).
- L196 `send_renewal_reminders(self)` (function) — Remind every ``active`` subscription renewing within ``prerenewal_days``.
- L230 `_remind_subscription(sub, now, cfg, send_templated_email)` (function) — Send the pre-renewal reminder once per period for one subscription.
- L280 `_parse_dt(raw)` (function) — Parse an ISO stamp into an aware datetime (``None`` if missing/unparseable).
