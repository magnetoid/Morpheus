---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-02T18:07:52'
updated: '2026-06-02T18:07:52'
---

# plugins/installed/seo/services/meta.py

Symbols in `plugins/installed/seo/services/meta.py`.

- L22 `resolve_meta(*, obj: Any | None=None, fallback_title: str='', fallback_description: str='', fallback_image: str='', canonical_url: str='', og_type: str='website')` (function) — Merge per-object SeoMeta + native model SEO fields + fallbacks.
- L132 `_structured_data_for(obj: Any, *, title: str, description: str, image: str)` (function) — Generate sensible JSON-LD for known model types. Empty dict if unknown.
- L174 `autofill_meta_for(obj: Any)` (function) — If the merchant left meta fields blank, fill them with sensible defaults
