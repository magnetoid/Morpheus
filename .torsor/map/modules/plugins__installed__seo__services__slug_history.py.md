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

# plugins/installed/seo/services/slug_history.py

Symbols in `plugins/installed/seo/services/slug_history.py`.

- L32 `public_path_for(obj, *, slug: str | None=None)` (function) — The storefront path for ``obj``, or '' when the object has no public URL.
- L46 `record_slug_change(obj, *, old_slug: str, new_slug: str)` (function) — Store the old path and, unless the merchant turned it off, 301 it.
- L79 `_mint_redirect(old_path: str, new_path: str)` (function)
- L102 `_repoint_existing(old_path: str, new_path: str)` (function)
- L119 `_auto_redirect_enabled()` (function)
