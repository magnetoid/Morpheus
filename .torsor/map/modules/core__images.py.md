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

# core/images.py

Symbols in `core/images.py`.

- L52 `_config(key: str, default)` (function) — Read one catalog image setting, cross-process fresh. Never raises.
- L72 `aspect_ratio_key()` (function) — The configured ratio key, guaranteed to be one of `ASPECT_RATIOS`.
- L78 `aspect_ratio_css()` (function) — The CSS `aspect-ratio` value, e.g. `'1 / 1'`.
- L83 `aspect_ratio_float()` (function) — Width / height, or None for `original` (no imposed ratio).
- L95 `fit_mode()` (function) — `'cover'` or `'contain'` — how the image sits inside the frame.
- L101 `quality()` (function) — Encoder quality for generated variants, clamped to a sane band.
- L114 `crop_to_ratio()` (function) — True when generated variants should be CROPPED to the ratio.
- L124 `_raw_config()` (function) — The stored catalog config dict, or {} — so callers can tell an explicit
- L139 `configured_display_settings()` (function) — The merchant's EXPLICIT frame choice, or None if they have not made one.
- L155 `display_settings()` (function) — Everything a template needs, in one read.
