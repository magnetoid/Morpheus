---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-02T18:07:52'
updated: '2026-06-02T18:07:52'
---

# plugins/installed/seo/services/audit.py

Symbols in `plugins/installed/seo/services/audit.py`.

- L22 `audit_product(product)` (function) — Run SEO checks against a Product. Returns {score, issues, suggestions}.
- L242 `score_aeo(product)` (function) — Answer-Engine / Generative-Engine readiness score for a product.
- L435 `store_audit(product, result: dict)` (function)
- L452 `audit_all_products(*, limit: int=500)` (function) — Run audit_product on every active product. Returns count audited.
- L463 `suggest_internal_links_for(product, *, limit: int=3)` (function) — Return up to ``limit`` related products as link-suggestion dicts.
