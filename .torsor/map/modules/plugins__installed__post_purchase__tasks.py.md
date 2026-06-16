---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:58'
updated: '2026-06-13T00:49:58'
---

# plugins/installed/post_purchase/tasks.py

Symbols in `plugins/installed/post_purchase/tasks.py`.

- L26 `process_due_steps()` (function) — Pick up every JourneyStep where due_at <= now and dispatch.
- L54 `_dispatch_step(step)` (function) — Return 'sent' | 'skipped' on success, raise on failure.
- L74 `_send_tracking(step)` (function)
- L94 `_send_delivered_followup(step)` (function)
- L108 `_send_review_request(step)` (function)
- L122 `_send_nps_survey(step)` (function)
- L144 `_send_email(*, order, subject: str, body: str, kind: str)` (function) — Thin shim over Django's send_mail. The notifications plugin can
- L166 `_nps_token(order)` (function)
- L170 `_site_url()` (function)
