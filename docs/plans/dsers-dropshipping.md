# DSers dropshipping — the `dsers` app

*Spec written 2026-10-06 (v0.78.0). Status: shipping as the CSV bridge; the
DSers Open API connection is a follow-up gated on the owner's partner account.*

## 1. Overview

- **Goal:** let a Morpheus store fulfil orders through DSers (the AliExpress
  dropshipping tool) — map store products to AliExpress supplier items, hand
  paid orders to DSers, and bring the tracking numbers back so the shopper gets
  the normal "on its way" email and the order reaches *shipped*.
- **Target users:** the supernatural-shop merchant first; any store that
  opts in with `MORPHEUS_EXTRA_APPS=plugins.installed.dsers`.
- **Why now:** supernatural-shop sources from AliExpress via DSers and has no
  path from a Morpheus order to a DSers order other than retyping.

## 2. How DSers can be connected (researched 2026-10-06)

DSers integrates natively with Shopify, WooCommerce, Wix and a few
marketplaces. For any other platform it offers two things:

1. **DSers Open API — Channel App.** A sales channel registers as a DSers
   developer partner (dsers.dev), is reviewed (up to 15 business days), and
   only then receives the API reference, a sandbox and credentials. Nothing is
   public before approval, so it cannot be built or tested today.
2. **CSV bridge.** Documented and account-only: a product-mapping file
   (`import_products`: *Product id, SKU, Supplier url, Supplier SKU*) and an
   orders file (`import_orders`, 21 columns, strict address rules) uploaded in
   DSers → *CSV Upload*. DSers places and pays the AliExpress orders; the
   merchant then downloads the orders with AliExpress order numbers and
   tracking numbers.

**Decision:** build the CSV bridge now — it works for the merchant on day one
and needs no approval — shaped so the Channel App connection can be added
behind the same models and dashboard page later. The owner should register at
dsers.dev in parallel.

## 3. Data models (`plugins/installed/dsers/models.py`)

- **`SupplierLink`** — one per product (and per variant when the product has
  variants): `product` FK → `catalog.Product`, `variant` FK → `catalog.ProductVariant`
  (nullable), `supplier_url` (the AliExpress product URL), `supplier_sku`
  (the AliExpress SKU/attribute id DSers expects), `notes`, timestamps.
  Unique on (`product`, `variant`). Edited on the product form through a
  contributed card (`PRODUCT_FORM_CARDS` / `PRODUCT_FORM_SAVED`).
- **`OrderSync`** — the DSers-side state of one order, OneToOne → `orders.Order`
  (`related_name='dsers_sync'`): `status` (*exported, shipped, cancelled*),
  `batch_id` (UUID of the export), `exported_at`, `supplier_order_number`
  (AliExpress order no.), `tracking_number`, `carrier`, `imported_at`, `note`.
  Tracking itself is written where the platform owns it — `Order.ship()` and an
  `orders.Fulfillment` row — never duplicated here beyond the audit copy.

No parallel order/return/fulfilment table (one concept, one owner).

## 4. Features and acceptance

- [ ] **Product mapping.** Product form card listing the product (or each
  variant) with *Supplier URL* + *Supplier SKU* inputs; saved via
  `PRODUCT_FORM_SAVED`. Dashboard button downloads `import_products.csv` for
  every link, in DSers' column order.
  *Acceptance:* card appears only while the app is enabled; saving the form
  writes/updates `SupplierLink`; the CSV has exactly the documented headers.
- [ ] **Order export.** Dashboard page lists *awaiting export* (paid, status
  confirmed/processing, not yet exported, at least one physical line). "Export
  to DSers" downloads `import_orders.csv`: one row per physical line, headers in
  DSers' order, addresses normalised (special characters stripped, phone
  reduced to digits and `+`, two-letter country codes expanded to full English
  names, `state`→Province, `postal_code`→Zip), `Order memo` from settings. Each
  exported order gets an `OrderSync(status='exported')`; a *confirmed* order
  moves to *processing* when the setting says so.
  *Acceptance:* unit tests on the CSV builder (headers, row count, normalisation,
  country expansion), eligibility (unpaid, cancelled, digital-only and already
  exported orders excluded), idempotence (second export excludes exported orders).
- [ ] **Tracking import.** Upload DSers' orders export (or any CSV with an
  order-number column and a tracking-number column; AliExpress order number
  and carrier picked up when present). For each matching order: `Order.ship(
  tracking_number)` when the state allows, a `Fulfillment(in_transit)` with
  carrier + tracking URL, `OrderSync(status='shipped')`. Summary of shipped /
  skipped rows with reasons.
  *Acceptance:* a shipped order fires `ORDER_FULFILLED` (the existing "on its
  way" email) once; unknown order numbers and already-shipped orders are
  reported, not errors; a row with no tracking number is skipped.
- [ ] **Needs attention.** Orders exported then cancelled in Morpheus
  (`ORDER_CANCELLED` subscriber flips `OrderSync` to *cancelled*) are listed so
  the merchant cancels them in DSers too.
- [ ] **Settings → Apps → DSers.** `order_memo` (text sent to suppliers),
  `tracking_url_template` (default 17TRACK, `{tracking}` placeholder),
  `mark_processing_on_export` (bool, default on). Every key has a reader
  (`core/tests/test_settings_keys_have_readers.py`).

## 5. Constraints

- Plugin owns everything (`plugins/installed/dsers/`); appears elsewhere only by
  contribution. Cross-plugin reads: `orders.Order/OrderItem/Fulfillment`,
  `catalog.Product/ProductVariant` — both declared in `requires`.
- Opt-in app (`MORPHEUS_EXTRA_APPS`), like `booking_marketplace`; CI's test job
  adds it to `MORPHEUS_EXTRA_APPS` so its suite runs.
- No new dependencies. Country names come from a bundled ISO-3166 table.
- Dashboard views: `@staff_member_required` + `@require_capability('orders.write')`
  (an existing capability — a new one would deny everyone under enforcement).
- `migrations/__init__.py` present (the invisible-migrations landmine).

## 6. Security and privacy

- The orders CSV carries customer PII (name, address, phone, email); it is a
  staff-only download over HTTPS and is not stored on disk by Morpheus.
- Uploaded tracking CSVs are parsed in memory; order numbers are matched
  exactly; nothing in the file can change prices, statuses other than
  processing→shipped, or other orders.
- Supplier URLs are stored as text and rendered as links only on the staff
  product form (escaped).

## 7. Out of scope (deliberately)

- Automatic order push / tracking pull over the DSers Open API (needs the
  partner account; add `services/api.py` behind the same `OrderSync` later).
- Product import from AliExpress (titles, images, prices) — DSers' own import
  does this on their side; images are handled outside Morpheus anyway.
- Supplier cost / margin tracking, inventory sync from AliExpress stock,
  automatic currency conversion.
- Address validation against AliExpress' city/province lists (DSers reports
  those failures; the merchant corrects in DSers).

## 8. Open questions for the owner

- Register as a DSers developer (dsers.dev → *Create account* → submit) so the
  Channel App path can be built; approval is reported within 15 business days.
- Confirm the exact headers of DSers' downloadable templates against the ones
  documented here (DSers may rename a column; the importer is header-tolerant,
  the exporter is not).
