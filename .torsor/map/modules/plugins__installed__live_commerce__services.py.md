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

# plugins/installed/live_commerce/services.py

Symbols in `plugins/installed/live_commerce/services.py`.

- L6 `upcoming_or_live()` (function) — Scheduled + live events, soonest first — for the teaser and list header.
- L13 `past_events(limit: int=24)` (function) — Ended events, most recent first.
- L20 `featured_teaser()` (function) — The single event to tease on the storefront (live wins, else next scheduled).
- L26 `utm_link(product, campaign: str)` (function) — Storefront product URL tagged so live-driven conversions attribute via UTM.
- L31 `set_status(event, status: str)` (function) — Transition an event's status, firing the matching hook on real changes.
