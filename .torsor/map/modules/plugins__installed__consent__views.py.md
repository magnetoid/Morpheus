---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-02T18:07:52'
updated: '2026-06-02T18:07:52'
---

# plugins/installed/consent/views.py

Symbols in `plugins/installed/consent/views.py`.

- L16 `_safe_referer(request: HttpRequest)` (function) — Return the referer iff it points back at our host, else '/'.
- L30 `save(request: HttpRequest)` (function) — Record a consent decision + bounce back to the referer.
- L61 `preferences(request: HttpRequest)` (function) — Standalone settings page (footer link) so customers can change
