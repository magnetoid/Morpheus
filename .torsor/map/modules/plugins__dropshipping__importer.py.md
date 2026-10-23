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

# plugins/dropshipping/importer.py

Symbols in `plugins/dropshipping/importer.py`.

- L37 `SupplierVariant` (class)
- L47 `SupplierProduct` (class)
- L58 `ImportResult` (class)
- L65 `sale_price(cost: Decimal, markup: Decimal, *, charm: bool=True)` (function) — ``cost × markup`` to the cent; with ``charm``, up to the next ``x.99``.
- L73 `clean_description(html_text: str)` (function) — Supplier HTML on the catalogue's allowlist: no scripts, styles or images.
- L81 `store_currency()` (function) — The currency the store sells in: what its active products are priced in.
- L102 `_sku(prefix: str, raw: str, fallback: str)` (function)
- L107 `_unique_variant_sku(sku: str)` (function)
- L117 `import_product(spec: SupplierProduct, *, markup: Decimal, currency: str, charm: bool=True)` (function) — Create the draft product, its variants and photos; return the variant map.
