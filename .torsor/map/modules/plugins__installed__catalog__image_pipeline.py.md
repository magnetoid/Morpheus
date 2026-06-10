---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-09T21:57:01'
updated: '2026-06-09T21:57:01'
---

# plugins/installed/catalog/image_pipeline.py

Symbols in `plugins/installed/catalog/image_pipeline.py`.

- L37 `_pillow_supports_avif()` (function) — True iff this Pillow build can encode AVIF.
- L51 `_settings()` (function) — Pull the catalog plugin's image defaults from PluginConfig.
- L108 `_downgrade_avif_if_unsupported(out: dict)` (function) — AVIF needs a Pillow build linked against libavif. Fall back to WebP
- L120 `_ext_for(fmt: str)` (function)
- L124 `_pil_format(fmt: str)` (function)
- L128 `generate_pdp_variant(product_image)` (function) — Resize + re-encode `product_image.image` and store it on
