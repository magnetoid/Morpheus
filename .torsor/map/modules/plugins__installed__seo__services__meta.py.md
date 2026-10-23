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

# plugins/installed/seo/services/meta.py

Symbols in `plugins/installed/seo/services/meta.py`.

- L22 `_store_default_social_image()` (function) — URL of the core-wide default social image (Settings → General → Default
- L35 `brand_name(settings_row=None)` (function) — The merchant's brand for title suffixes — the SAME resolution the
- L65 `format_document_title(page_title: str, *, category: str='', settings_row=None)` (function) — Build the branded ``<title>`` the way Yoast/RankMath do: apply the
- L114 `_clamp_on_word(text: str, max_len: int)` (function) — Clamp ``text`` to ``max_len`` without cutting inside a word.
- L122 `_template_layer(page_kind: str, obj, meta, autofilled: bool, native, title: str, description: str)` (function) — The SeoTemplate layer: fills what the merchant left empty (or, in `all`
- L144 `resolve_meta(*, obj: Any | None=None, fallback_title: str='', fallback_description: str='', fallback_image: str='', canonical_url: str='', og_type: str='website', page_kind: str='')` (function) — Merge per-object SeoMeta + native model SEO fields + fallbacks.
- L311 `_visual_schema_blocks(meta)` (function) — JSON-LD blocks from the visual schema editor's stored entries, or None.
- L321 `_structured_data_for(obj: Any, *, title: str, description: str, image: str)` (function) — Generate sensible JSON-LD for known model types. Empty dict if unknown.
- L366 `autofill_meta_for(obj: Any)` (function) — If the merchant left meta fields blank, fill them with sensible defaults
