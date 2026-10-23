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

# core/utils/site.py

Symbols in `core/utils/site.py`.

- L14 `site_base_url()` (function) — Public site root with a trailing slash.
- L26 `store_name()` (function) — The merchant's brand — what the *business* is called.
- L49 `store_slug(suffix: str='')` (function) — Machine-readable form of :func:`store_name`, for manifest ``name``
- L60 `store_contact_email()` (function) — Public contact address for the store, or ``''`` when unset.
- L77 `store_logo_url()` (function) — Absolute URL of the merchant's logo, or ``''`` when none is set.
- L95 `absolutize(url: str)` (function) — Make a site-relative URL (``/media/…``) absolute against
