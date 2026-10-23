---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:50'
updated: '2026-10-23T04:51:50'
rules: []
---

# plugins/installed/book_product/services_copy.py

Symbols in `plugins/installed/book_product/services_copy.py`.

- L23 `CopyGenerationError` (class) — The AI provider was unavailable, or returned nothing usable as copy.
- L27 `_curated_model(kind)` (function)
- L33 `_subject_for(taxonomy: str, slug: str)` (function) — Return ``(subject, context_line)`` describing the page being written.
- L84 `build_prompt(subject: str, context_line: str, *, mode: str='generate', existing: str='')` (function)
- L106 `generate_copy(taxonomy: str, slug: str='', *, mode: str='generate', existing: str='')` (function) — Generate ``{description, meta_title, meta_description}`` for one page.
