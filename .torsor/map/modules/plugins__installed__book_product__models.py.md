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

# plugins/installed/book_product/models.py

Symbols in `plugins/installed/book_product/models.py`.

- L18 `PrintType` (class)
- L29 `PaperType` (class)
- L38 `_CuratedTaxonomy` (class) — Shared shape for the curated, multi-value book taxonomies (Genre, Topic).
- L64 `__str__(self)` (method)
- L67 `save(self, *args, **kwargs)` (method)
- L75 `Genre` (class) — A literary genre (Fiction, Poetry, Essays, …). The primary book taxonomy
- L80 `Topic` (class) — A subject/theme tag (WWII, grief, space exploration). A second, flat axis
- L85 `BookProduct` (class) — Book-specific attributes for a catalog Product (one-to-one).
- L144 `__str__(self)` (method)
- L147 `language_editions(self)` (method) — Every edition of this work (the original + all translations),
- L162 `BookTaxonomy` (class) — The taxonomies derived from BookProduct string fields — the only kinds
- L173 `BookRootTaxonomy` (class) — Every taxonomy kind that has a *listing* page, keyed for BookTaxonomyRoot.
- L191 `BookTaxonomyTerm` (class) — Per-term SEO/metadata overlay for a book taxonomy value.
- L216 `__str__(self)` (method)
- L220 `BookTaxonomyRoot` (class) — The landing page for a whole taxonomy kind (e.g. /authors/, /genres/).
- L240 `__str__(self)` (method)
