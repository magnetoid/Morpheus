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

# plugins/installed/booking_marketplace/email.py

Symbols in `plugins/installed/booking_marketplace/email.py`.

- L22 `_store_name()` (function)
- L28 `_from()` (function)
- L32 `_ops_inbox()` (function) — Where a listing without an owner's email sends its alerts: the configured
- L40 `_owner_email(vendor)` (function)
- L45 `_host_recipient(enquiry)` (function) — Vendor owner's email if available, else the ops inbox.
- L51 `_selection_lines(enquiry)` (function) — Human-readable summary of the structured selection captured on the lead.
- L67 `_send(subject: str, body: str, to: str, *, reply_to: str='')` (function)
- L80 `send_enquiry_host_notification(enquiry)` (function)
- L95 `send_enquiry_confirmation(enquiry)` (function)
- L106 `notify_enquiry(enquiry)` (function) — Fire both emails, best-effort. Safe to call from the request path.
- L115 `_stay_host_recipient(enquiry)` (function) — Property owner's email if available, else the configured ops inbox.
- L122 `send_stay_enquiry_host_notification(enquiry)` (function)
- L150 `send_stay_enquiry_confirmation(enquiry)` (function)
- L161 `notify_stay_enquiry(enquiry)` (function) — Tell the host and the guest about a stay enquiry (never raises).
- L175 `notify_booking(booking)` (function) — Tell the guest and the host about an experience booking (never raises).
- L207 `notify_stay_booking(booking)` (function) — Tell the guest and the host about a stay booking (never raises).
