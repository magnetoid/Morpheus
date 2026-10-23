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

# core/self_improvement/collectors/seo_gap.py

Symbols in `core/self_improvement/collectors/seo_gap.py`.

- L49 `SeoGapCollector` (class)
- L52 `run(self)` (method)
- L66 `_product_missing_meta(self, Product)` (method)
- L81 `_image_missing_alt(self, ProductImage)` (method)
- L95 `_page_missing_meta(self, Page)` (method)
- L113 `_sample(rows, *, skip: set[str])` (method) — Up to SAMPLE_CAP rows whose pk isn't in `skip`.
- L130 `_overlay_described(Model)` (method) — `object_id`s of this model carrying a non-empty `SeoMeta.description`.
- L154 `_active(Product)` (method) — Narrow to live products. Status field name varies by codebase
- L163 `_product_model()` (method)
- L172 `_product_image_model()` (method)
- L181 `_page_model()` (method)
