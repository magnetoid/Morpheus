---
type: active-context
status: active
tags:
- active
links: []
created: '2026-06-04T02:04:46'
updated: '2026-06-04T02:04:46'
---

# Active Context

## Current focus
"Book Product" app COMPLETE + shipped (goal delivered). book_product plugin: BookProduct OneToOne→Product (author, print/paper type, pages, cover_pdf, dims, etc.); Settings → Product Types page; dashboard product-edit Book widget; three.js 3D cover-PDF viewer (drag/rotate) in dashboard + PDP; storefront PDP shows book data from the MODEL not meta (book_specs model-first); full GraphQL control (bookProduct query + setBookProduct mutation, catalog.write scope); fail-soft data migration book.* metafields → model. ADR 0006 records the product-type-extension pattern. Also shipped this session: full-bleed mega menu + Authors dropdown; fixed live mega/drawer overflow + checkout money-dict + caching unification + shipping panel fold.

## Open questions
Book Product follow-ups (deferred, noted in ADR 0006 + plan): (1) retire book.* metafields once author_detail + PLP author/publisher filters move to the BookProduct model (they still read metafields, so kept); (2) optional formal contribute_product_panels() hook to remove the one pragmatic admin_dashboard guard; (3) register a /book-product/ URL if a standalone 3D-preview asset endpoint is wanted. Also still open from earlier: PAYMENTS settings de-dup; pre-existing cloudflare/tests/test_purge.py failures (baseline); ecommerce.py:655 cfg.config_data dead-read. Verify book widget/3D on a real product in prod after deploy.
