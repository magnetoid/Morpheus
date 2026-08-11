# eco_impact — book production footprint + plant-a-tree offset

**Status:** in build (2026-07-19). New plugin. MINOR release.

## What & why

Show each book's **production footprint** (wood/paper used + embodied CO₂,
derived from its physical attributes) on the storefront product page, and let
shoppers **opt in at checkout to "plant a tree"** — a configurable surcharge
that funds reforestation to compensate the order's carbon. The tree money is a
**tracked fund the merchant fulfills** (records trees pledged per order + a
store total; no external provider API in v1). Copy stays honest — "we direct
this to reforestation", never a fabricated per-order guarantee.

User decisions (2026-07-19):
1. Tree charge = **opt-in add-on at checkout** (via `CART_CALCULATE_BREAKDOWN`).
2. Fulfillment = **tracked fund, merchant fulfills** (no external API).

## Boundary (overlap audit — house rule)

- **`smart_shipping` already owns shipping-lane carbon** (`CarrierEmission`,
  per-rate g CO₂e, "lowest carbon" badge). `eco_impact` MUST NOT recompute
  shipping carbon. It owns a *different* number: the **production** footprint of
  making the book (paper → wood, print embodied CO₂), which is
  address-independent and belongs on the PDP.
- The tree offset is a flat opt-in ("plant 1 tree, +price, offsets ~X kg CO₂")
  sized to comfortably cover a typical book order's production + shipping
  footprint — so it "compensates the carbon" without coupling to
  smart_shipping internals.
- No existing eco/carbon/green/tree plugin → new plugin justified.
- `requires: book_product` (reads `Book.weight_g / width_mm / height_mm /
  spine_mm / page_count / print_type`); falls back to `catalog.Product.weight`.
  Cross-plugin data read is via book_product's own resolver/hook, never a model
  import from a sibling.

## Footprint math (`footprint.py`, pure, no DB)

Inputs from `Book` (fallback `Product.weight` kg → g):
- `paper_mass_g` ≈ `weight_g × paper_fraction` (default 0.85; most of a book's
  mass is paper). If no `weight_g`: estimate from `page_count`, page area
  (`width_mm×height_mm`), and a gsm default per `print_type`.
- `wood_g` = `paper_mass_g × wood_factor` (default 2.5 — ~2.5 kg wood per kg
  virgin paper; tunable).
- `co2_production_kg` = `paper_mass_kg × co2_per_kg_paper` (default 1.3) +
  `print_overhead_kg` (default 0.3). Industry book-production avg ≈ 1–2.7 kg.
- Display helpers: `sheets` (paper_mass_g / A4-sheet ≈ 5 g), `tree_fraction`
  (co2 / kg_co2_per_tree).

All factors are plugin settings so a merchant can tune to their supplier data.
Every constant cites its basis in a comment; no fabricated precision — the UI
says "estimated".

## Components (all under `plugins/installed/eco_impact/`)

- `footprint.py` — pure calc (above).
- `services.py` — `impact_for_product(product_or_id)` → dict for PDP;
  `record_pledge(order, trees, amount)` idempotent; `store_totals()`.
- `models.py` — `TreePledge(order FK OneToOne, trees, amount, created_at)`;
  migration.
- `app.py` — manifest (`requires=['book_product']`), settings schema
  (`show_on_pdp`, `tree_price`, `kg_co2_per_tree`, factor tunables, copy),
  `ready()` wiring:
  - PDP `StorefrontBlock(slot=<pdp slot>)` → eco badge (gated on `show_on_pdp`).
  - checkout opt-in widget contribution (checkout slot).
  - `CART_CALCULATE_BREAKDOWN` subscriber → adds the tree surcharge when opted in.
  - `ORDER_PAID` subscriber → `record_pledge` (idempotent).
  - dashboard page/KPI → store trees-pledged total.
- **Storefront "Save the planet" page** (`/save-the-planet/`, eco_impact-owned
  view + template, linked via a `footer_extra`/nav StorefrontBlock so it's
  disable-safe): hero + live store totals (trees pledged, kg CO₂ offset, kg
  wood), the calculation methodology, a privacy-safe contributor count
  ("N readers have planted trees with us"), and a shop CTA.
- templates: PDP badge, checkout opt-in, save-the-planet page, dashboard summary.
- **Follow-up (confirm, not built yet):** award loyalty points to buyers who
  opt into planting (would ride a hook so eco_impact never imports
  loyalty_points).
- tests: footprint math (fallbacks), breakdown adds surcharge only when opted
  in, order records exactly one pledge (idempotent), disable-safety.

## Disable test

Delete/disable `eco_impact` → PDP badge, checkout opt-in, the surcharge line,
and the dashboard total all vanish (all contributed via blocks/hooks; nothing
hard-coded in storefront/theme/admin_dashboard).

## Verify

`DATABASE_URL='sqlite:///:memory:' python manage.py test
plugins.installed.eco_impact`; ruff + template compile; MINOR version bump +
release note; live smoke of a book PDP + checkout.
