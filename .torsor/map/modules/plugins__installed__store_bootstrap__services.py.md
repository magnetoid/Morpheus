---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:58'
updated: '2026-06-13T00:49:58'
---

# plugins/installed/store_bootstrap/services.py

Symbols in `plugins/installed/store_bootstrap/services.py`.

- L68 `BootstrapResult` (class)
- L80 `_hash_prompt(prompt: str)` (function)
- L84 `_apply_brand_voice(brand: dict)` (function) — Persist the generated brand-voice config into the ai_content plugin.
- L112 `_create_categories(spec: list[dict])` (function) — Resolve categories. Returns a {name: Category} map for product linking.
- L143 `_create_products(spec: list[dict], category_map: dict[str, Any])` (function) — Create active products linked to their named category.
- L189 `bootstrap_store_from_prompt(prompt: str)` (function) — Run the full bootstrap. Returns a BootstrapResult — never raises.
