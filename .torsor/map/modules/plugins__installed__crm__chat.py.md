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

# plugins/installed/crm/chat.py

Symbols in `plugins/installed/crm/chat.py`.

- L15 `thread_by_id(thread_id: str)` (function) — Look up a thread by id, returning None for empty/malformed UUIDs (never
- L31 `resolve_thread(request, thread_id: str='', email: str='')` (function) — Find the customer's current thread (by id, then by logged-in customer),
- L64 `_link_lead(thread)` (function) — Capture an anonymous emailer as a CRM Lead (chat → pipeline).
- L80 `post_customer_message(thread, body: str)` (function) — Append a customer message; reopen + flag unread for staff. Notifies staff
- L98 `_notify_staff(thread, msg)` (function) — Email active staff that a support thread needs a reply. Best-effort.
- L126 `post_staff_reply(thread, body: str, staff_user=None)` (function) — Append a staff reply; clear the unread flag.
