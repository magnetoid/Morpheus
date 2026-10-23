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

# plugins/installed/tracking/models.py

Symbols in `plugins/installed/tracking/models.py`.

- L60 `TrackingSettings` (class) — Singleton — merchant config for GA4 + GTM.
- L163 `__str__(self)` (method)
- L167 `get_solo(cls)` (method) — Return the singleton row, creating it with defaults if missing.
- L185 `event_enabled(self, name: str)` (method)
- L188 `is_path_blocked(self, path: str)` (method)
- L195 `GA4EventLog` (class) — Append-only record of every server-side Measurement Protocol hit.
- L232 `__str__(self)` (method)
