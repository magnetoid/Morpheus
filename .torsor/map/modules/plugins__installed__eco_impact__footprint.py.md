---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:51'
updated: '2026-10-23T04:51:51'
rules: []
---

# plugins/installed/eco_impact/footprint.py

Symbols in `plugins/installed/eco_impact/footprint.py`.

- L38 `_factors(overrides: dict | None)` (function) — Shallow-merge caller overrides onto DEFAULTS (gsm_by_type merged too).
- L49 `estimate_paper_mass_g(*, weight_g: float | None=None, product_weight_kg: float | None=None, page_count: int | None=None, width_mm: int | None=None, height_mm: int | None=None, print_type: str='paperback', factors: dict | None=None)` (function) — Best-effort paper (text-block) mass in grams. 0.0 when undeterminable.
- L79 `impact(*, weight_g: float | None=None, product_weight_kg: float | None=None, page_count: int | None=None, width_mm: int | None=None, height_mm: int | None=None, print_type: str='paperback', factors: dict | None=None)` (function) — Full production-footprint estimate for one book.
