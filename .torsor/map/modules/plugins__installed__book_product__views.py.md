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

# plugins/installed/book_product/views.py

Symbols in `plugins/installed/book_product/views.py`.

- L49 `_active_products(books)` (function)
- L53 `_shelf_description(label: str, value: str, products: list, count: int)` (function) — A meta description written from the books themselves.
- L69 `_term_description(term)` (function) — The merchant's meta description, else the term's own editorial copy.
- L83 `_jsonld_items(products)` (function) — [{name, url, image}] — the ItemList the SEO graph publishes for the shelf.
- L98 `_render(request, label, value, products, *, term=None, index_url=None)` (function)
- L167 `_slug_facet(request, field, slug, label, *, taxonomy=None, order_by='-product__is_featured')` (function) — Landing page for a free-text book field matched by slugify(value).
- L196 `_value_facet(request, field, value, label, display, *, stored=None)` (function) — Landing page for an enum-ish book field (print_type / language).
- L220 `publisher_detail(request, slug)` (function)
- L224 `imprint_detail(request, slug)` (function)
- L228 `series_detail(request, slug)` (function)
- L235 `format_detail(request, value)` (function)
- L243 `language_detail(request, value)` (function) — One page per language, named by its code.
- L293 `_index_description(root, label: str)` (function) — The merchant's index copy, else a plain line that names no store.
- L304 `_in_print_counts(key: str)` (function) — `{slug: books in print}` for a free-text field — one query, not one per value.
- L324 `_taxonomy_root(request, *, key, label)` (function) — An index of every value with at least one book in print.
- L401 `_curated_root(request, *, model, key, label, detail_prefix)` (function)
- L443 `_curated_detail(request, *, model, slug, label, index_url)` (function)
- L455 `genres_root(request)` (function)
- L461 `topics_root(request)` (function)
- L467 `genre_detail(request, slug)` (function)
- L473 `topic_detail(request, slug)` (function)
- L479 `authors_root(request)` (function)
- L483 `publishers_root(request)` (function)
- L487 `series_root(request)` (function)
- L491 `imprints_root(request)` (function)
