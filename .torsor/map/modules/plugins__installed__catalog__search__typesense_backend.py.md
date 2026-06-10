---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-10T20:08:49'
updated: '2026-06-10T20:08:49'
---

# plugins/installed/catalog/search/typesense_backend.py

Symbols in `plugins/installed/catalog/search/typesense_backend.py`.

- L57 `run(q: str, *, page: int=1, per_page: int=24, filter_by: str='', sort_by: str='')` (function) — Search the Typesense collection. Raises on failure (the
- L108 `ensure_collection()` (function) — Idempotent. Creates the collection on first run; no-ops thereafter.
- L139 `upsert_product(product)` (function) — Mirror one Product into Typesense. Called from PRODUCT_CREATED/
- L153 `delete_product(product_id: str)` (function)
- L164 `reindex_all(batch_size: int=500)` (function) — Full reindex — drop + recreate the collection, batch-insert all
- L200 `_serialize(product)` (function) — Project one Product → Typesense document shape.
- L229 `_client()` (function)
- L248 `_collection_name()` (function)
- L253 `_is_active()` (function)
