---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-09T21:57:01'
updated: '2026-06-09T21:57:01'
---

# plugins/installed/affiliates/widgets.py

Symbols in `plugins/installed/affiliates/widgets.py`.

- L25 `_safe_href(url: str)` (function) — Defense-in-depth at the single public-boundary point: only a root-relative
- L41 `_active_products_qs()` (function)
- L47 `resolve_products(widget)` (function) — The ordered list of public Products this widget renders.
- L82 `widget_ref_code(widget)` (function) — The affiliate ref code every product link in this widget uses.
- L101 `product_pdp_path(product)` (function) — Internal storefront PDP path for a product (no host).
- L111 `product_click_url(product, ref_code: str, *, base: str='')` (function) — Absolute (or root-relative) click URL for a product card.
- L126 `_image_url(product)` (function) — Public cover image URL (prefers the WebP variant). '' when none.
- L141 `_fmt_money(value)` (function) — Display string for a Money value via the canonical storefront filter
- L154 `_price_str(product)` (function) — Display price as a plain string (e.g. '$19.99').
- L159 `serialize_product(product, ref_code: str, *, base: str='')` (function) — PUBLIC, cross-origin-safe product dict. See module security contract.
- L178 `serialize_widget(widget, *, base: str='')` (function) — Full public payload for the JSON endpoint + JS snippet.
