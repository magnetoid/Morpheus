---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:58'
updated: '2026-06-13T00:49:58'
---

# plugins/installed/seo/services/meta.py

Symbols in `plugins/installed/seo/services/meta.py`.

- L22 `brand_name()` (function) — The merchant's brand for title suffixes — the SAME resolution the
- L47 `format_document_title(page_title: str, *, category: str='')` (function) — Build the branded ``<title>`` the way Yoast/RankMath do: apply the
- L89 `resolve_meta(*, obj: Any | None=None, fallback_title: str='', fallback_description: str='', fallback_image: str='', canonical_url: str='', og_type: str='website')` (function) — Merge per-object SeoMeta + native model SEO fields + fallbacks.
- L214 `_structured_data_for(obj: Any, *, title: str, description: str, image: str)` (function) — Generate sensible JSON-LD for known model types. Empty dict if unknown.
- L256 `autofill_meta_for(obj: Any)` (function) — If the merchant left meta fields blank, fill them with sensible defaults
