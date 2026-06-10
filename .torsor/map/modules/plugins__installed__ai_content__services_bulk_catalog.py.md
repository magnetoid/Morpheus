---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-10T20:08:49'
updated: '2026-06-10T20:08:49'
---

# plugins/installed/ai_content/services_bulk_catalog.py

Symbols in `plugins/installed/ai_content/services_bulk_catalog.py`.

- L43 `CatalogOpResult` (class)
- L53 `BulkRunResult` (class)
- L60 `rewrite(*, target: str, tone: str, product_ids: list, dry_run: bool=True)` (function) — Rewrite `target` on each product in the new `tone`.
- L85 `translate(*, target: str, language: str, product_ids: list, dry_run: bool=True)` (function) — Translate `target` into `language` (e.g. 'fr', 'es', 'de').
- L113 `expand(*, target: str, product_ids: list, dry_run: bool=True)` (function) — Expand a stub into 3-4 paragraphs of merchant-quality copy.
- L144 `_bulk_run(*, target: str, product_ids: list, op, dry_run: bool)` (function)
- L188 `_call_llm(user_prompt: str)` (function) — Call the LLM with brand-voice context. Returns (text, tokens_used).
