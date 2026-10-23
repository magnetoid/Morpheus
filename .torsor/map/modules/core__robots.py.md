---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:49'
updated: '2026-10-23T04:51:49'
rules: []
---

# core/robots.py

Symbols in `core/robots.py`.

- L33 `RobotsDocument` (class) — A mutable description of the rules every crawler group receives.
- L44 `__init__(self)` (method)
- L49 `disallow(self, path: str)` (method) — Block a path or path pattern (`/cart/`, `/*?*sort=`) for every group.
- L53 `allow(self, path: str)` (method) — Carve an exception out of a broader Disallow (`/cart/summary.json`).
- L57 `sitemap(self, url: str)` (method) — Advertise a sitemap (or sitemap index) at an absolute URL.
- L62 `disallowed(self)` (method)
- L66 `allowed(self)` (method)
- L70 `sitemaps(self)` (method)
- L74 `_append(target: list[str], value: str)` (function) — Add a trimmed, non-empty, not-already-present value.
