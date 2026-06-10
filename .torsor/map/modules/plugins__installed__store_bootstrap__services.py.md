---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-09T21:57:02'
updated: '2026-06-09T21:57:02'
---

# plugins/installed/store_bootstrap/services.py

Symbols in `plugins/installed/store_bootstrap/services.py`.

- L67 `BootstrapResult` (class)
- L79 `_hash_prompt(prompt: str)` (function)
- L83 `_apply_brand_voice(brand: dict)` (function) — Persist the generated brand-voice config into the ai_content plugin.
- L110 `_create_categories(spec: list[dict])` (function) — Resolve categories. Returns a {name: Category} map for product linking.
- L140 `_create_products(spec: list[dict], category_map: dict[str, Any])` (function) — Create active products linked to their named category.
- L185 `bootstrap_store_from_prompt(prompt: str)` (function) — Run the full bootstrap. Returns a BootstrapResult — never raises.
