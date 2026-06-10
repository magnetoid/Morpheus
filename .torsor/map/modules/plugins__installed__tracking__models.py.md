---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-10T20:08:50'
updated: '2026-06-10T20:08:50'
---

# plugins/installed/tracking/models.py

Symbols in `plugins/installed/tracking/models.py`.

- L60 `TrackingSettings` (class) — Singleton — merchant config for GA4 + GTM.
- L179 `__str__(self)` (method)
- L183 `get_solo(cls)` (method) — Return the singleton row, creating it with defaults if missing.
- L201 `event_enabled(self, name: str)` (method)
- L204 `is_path_blocked(self, path: str)` (method)
- L211 `GA4EventLog` (class) — Append-only record of every server-side Measurement Protocol hit.
- L248 `__str__(self)` (method)
