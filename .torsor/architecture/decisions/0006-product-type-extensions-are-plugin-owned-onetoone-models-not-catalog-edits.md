---
type: decision
status: accepted
tags:
- adr
links: []
created: '2026-06-04T02:04:31'
updated: '2026-06-04T02:04:31'
rules: []
---

# ADR 0006: Product-type extensions are plugin-owned OneToOne models, not catalog edits

## Context
The catalog Product has a flat product_type CharField and no per-type extension mechanism; book-specific data lived in loose book.* metafields. The user asked for a "Book Product" app extending products with book fields (author, print/paper type, pages, cover PDF, 3D preview), a Settings → Product Types page, a dashboard product-edit widget, storefront display, and full GraphQL control. Strawberry has no plugin type-extension, and the modularity contract forbids cross-plugin imports / editing core layers for a feature.

## Decision
A product-type extension is a plugin owning a OneToOne→catalog.Product model (BookProduct, related_name='book') plus all its own surfaces, contributed not hard-coded: a SettingsPanel under a 'product_types' settings category; a dashboard product-edit card whose data-fetch/save live in the plugin (book_product.dashboard.book_widget_context/save_book_fields) and are called guarded from admin_dashboard.product_edit (try/except, like bookvault); a StorefrontBlock for the PDP (self-gating template tag book_for_product resolves the row from the GraphQL product dict); and self-contained GraphQL (bookProduct query + setBookProduct mutation via register_graphql_extension, scoped catalog.write). A fail-soft data migration moves legacy book.* metafields onto the model. The storefront PDP reads the model first (book_specs model-first, metafield fallback) so book data shows from the model, not meta. ISBN/EAN/GTIN stay in the identifiers metafield namespace. three.js/PDF.js for the 3D cover load from unpkg via importmap (storefront CSP report-only; dashboard CSP widened for unpkg connect/worker-src).

## Consequences
Disabling/removing book_product removes every surface it added (widget, block, settings, GraphQL) with no dangling code, satisfying the disable test. Adding a `book` field to the GraphQL Product type was intentionally NOT done (would force catalog→book_product coupling); instead a top-level bookProduct query gives full GraphQL read, setBookProduct gives write. Future product types (apparel, vinyl, …) follow the same shape. Follow-ups: retire the book.* metafields once author_detail + PLP author/publisher filters move to the model (they still read metafields); a formal contribute_product_panels() hook would remove the one pragmatic admin_dashboard guard.
