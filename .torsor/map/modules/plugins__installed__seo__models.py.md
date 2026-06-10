---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-09T21:57:02'
updated: '2026-06-09T21:57:02'
---

# plugins/installed/seo/models.py

Symbols in `plugins/installed/seo/models.py`.

- L27 `SeoMeta` (class) — Per-object SEO override. Generic across any model in the platform.
- L83 `__str__(self)` (method)
- L87 `for_obj(cls, obj)` (method)
- L94 `Redirect` (class) — 301/302 alias from one path to another.
- L113 `__str__(self)` (method)
- L117 `SitemapEntry` (class) — Optional precomputed sitemap entry. Most callers should let the
- L151 `SiteSeoSettings` (class) — Singleton-style site-wide SEO defaults.
- L252 `__str__(self)` (method)
- L256 `get_solo(cls)` (method)
- L261 `SeoAuditResult` (class) — Per-object SEO score + diagnostics. Refreshed on demand or by beat task.
- L286 `TrackedKeyword` (class) — A keyword the merchant cares about, optionally tied to a target page.
- L303 `NotFoundLog` (class) — Aggregated 404 log — used to surface auto-redirect candidates.
