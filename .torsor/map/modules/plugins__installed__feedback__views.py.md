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

# plugins/installed/feedback/views.py

Symbols in `plugins/installed/feedback/views.py`.

- L40 `_decode_screenshot(data_url: str)` (function) — base64 data URL → ContentFile. Returns (file, skipped_reason).
- L59 `_recent_server_errors(limit: int=10)` (function) — Snapshot recent server-side errors so the ticket carries them forever.
- L84 `submit(request)` (function) — Create a ticket. Any signed-in staff member may report.
- L145 `ticket_list(request)` (function)
- L178 `ticket_detail(request, pk)` (function)
