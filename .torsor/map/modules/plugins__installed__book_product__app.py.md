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

# plugins/installed/book_product/app.py

Symbols in `plugins/installed/book_product/app.py`.

- L10 `BookProductPlugin` (class)
- L22 `ready(self)` (method)
- L95 `on_product_card_meta(self, value, product=None, **_)` (method)
- L100 `on_listing_facets(self, value, params=None, surface='', **_)` (method)
- L105 `on_seo_resolve_page(self, value, request=None, context=None, **kwargs)` (method) — Claim this app's storefront URLs for the SEO layer.
- L134 `on_product_form_cards(self, value, product=None, **kwargs)` (method) — Contribute the 'Book details' card. Shown for every product (any
- L148 `on_product_form_saved(self, product=None, post=None, files=None, **kwargs)` (method) — Persist the book fields submitted with the product form.
- L156 `contribute_dashboard_pages(self)` (method)
- L174 `contribute_storefront_blocks(self)` (method)
