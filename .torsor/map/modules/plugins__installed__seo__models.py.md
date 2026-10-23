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

# plugins/installed/seo/models.py

Symbols in `plugins/installed/seo/models.py`.

- L27 `SeoMeta` (class) — Per-object SEO override. Generic across any model in the platform.
- L157 `__str__(self)` (method)
- L161 `for_obj(cls, obj)` (method)
- L168 `Redirect` (class) — One rule mapping an old path to a new one — or to nothing (410).
- L229 `__str__(self)` (method)
- L235 `is_gone(self)` (method)
- L238 `save(self, *args, **kwargs)` (method) — Normalise the paths and collapse the chain before storing.
- L267 `SlugHistory` (class) — Every public path an object has ever had.
- L290 `__str__(self)` (method)
- L294 `IndexRule` (class) — What a query parameter does to a page's indexability.
- L361 `__str__(self)` (method)
- L364 `save(self, *args, **kwargs)` (method) — Normalise on the model, not in the view.
- L378 `SeoTemplate` (class) — One title/description pattern for a whole page kind.
- L436 `__str__(self)` (method)
- L440 `save(self, *args, **kwargs)` (method)
- L446 `SitemapEntry` (class) — Optional precomputed sitemap entry. Most callers should let the
- L480 `SiteSeoSettings` (class) — Singleton-style site-wide SEO defaults.
- L599 `__str__(self)` (method)
- L603 `get_solo(cls)` (method)
- L608 `SeoAuditResult` (class) — Per-object SEO score + diagnostics. Refreshed on demand or by beat task.
- L633 `TrackedKeyword` (class) — A keyword the merchant cares about, optionally tied to a target page.
- L650 `NotFoundLog` (class) — Aggregated 404 log — used to surface auto-redirect candidates.
