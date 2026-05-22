# Spec — ProductVariant Shopify parity

> What's missing from Morpheus' variant model compared to Shopify (the
> reference implementation for ecommerce variant semantics), and the
> incremental path to close the gap. Same shape as the other plan
> docs — every tier is a discrete, shippable commit.

## 1. The 2026 Shopify variant model in one paragraph

A Shopify ProductVariant is a purchasable version of a product (e.g.
"Red T-Shirt, size XL"). Each variant has its own SKU, price,
compare-at-price, barcode, position, taxability, and up to ~3
selected options (color, size, material). **Fulfillment data
(shipping requirement, weight, customs info, stock-tracking flag)
lives on a separate `InventoryItem` record linked 1:1 to the
variant** — this decoupling is what lets Shopify cleanly express
"this variant is digital" (the InventoryItem has
`requiresShipping=false, tracked=false`) vs "physical"
(`requiresShipping=true, tracked=true`) vs "virtual / service"
(`requiresShipping=false, tracked=false`, but the merchant fulfills
manually). Each variant can also have its own media gallery (separate
from the parent product's), selling plans (subscriptions), and bundle
components.

## 2. Current Morpheus `ProductVariant` (plugins/installed/catalog/models.py:399)

| Field | Type | Per-variant? | Shopify parity |
|---|---|---|---|
| `id` (UUID) | UUIDField | ✅ | ✅ matches |
| `product` (FK) | ForeignKey | ✅ | ✅ matches |
| `name` | CharField(200) | ✅ | ✅ ~= `title` |
| `sku` | CharField(100, unique) | ✅ | ✅ matches |
| `price` | MoneyField | ✅ | ✅ matches |
| `compare_at_price` | MoneyField | ✅ | ✅ matches `compareAtPrice` |
| `localized_prices` | JSONField | ✅ | ~= `contextualPricing` (Markets) |
| `cost_price` | MoneyField | ✅ | ~= `inventoryItem.unitCost` |
| `attribute_values` | M2M | ✅ | ~= `selectedOptions` |
| `image` | FK to ProductImage | ✅ | ❌ Shopify has multiple media per variant |
| `weight` | DecimalField | ✅ | ❌ Should live on InventoryItem |
| `is_active` | BooleanField | ✅ | ~= `availableForSale` (derived) |
| `sort_order` | PositiveIntegerField | ✅ | ✅ ~= `position` |

## 3. The gap — fields that Shopify has and Morpheus doesn't

### Critical (Tier 1) — block real ecommerce use cases

| Missing field | Shopify name | Why it matters | Suggested Morpheus shape |
|---|---|---|---|
| Per-variant shipping flag | `inventoryItem.requiresShipping` | **The user's exact ask** — virtual / digital variants don't need a shipping address at checkout | `requires_shipping` BooleanField on ProductVariant (skip the InventoryItem hop for now) |
| Backorder policy | `inventoryPolicy` (CONTINUE / DENY) | Lets the merchant accept orders after stock hits zero | `inventory_policy` CharField, choices=`['deny','continue']`, default=`'deny'` |
| Barcode / UPC | `barcode` | Required for retail / wholesale / POS integrations | `barcode` CharField(50, blank=True) |
| Per-variant taxability | `taxable` | EU VAT on digital products differs from physical; per-variant taxability solves cleanly | `is_taxable` BooleanField (defaults to parent's `is_taxable`) |
| Variant type | (implicit via `requiresShipping` + `tracked`) | **The user's exact ask** — digital / physical / virtual taxonomy per variant | `variant_type` CharField, choices=`['physical','digital','virtual']`, default=`'physical'` |
| Per-variant digital file | (Shopify ships digital products via separate app or `requiresShipping=false` + manual fulfillment) | A digital variant needs its own file — can't share with the parent if the parent has multiple format variants (e.g. PDF / EPUB / MOBI) | `digital_file` FileField, blank=True (overrides product.digital_file when set) |

### Useful (Tier 2) — nice to have

| Missing field | Shopify name | Why it matters | Suggested Morpheus shape |
|---|---|---|---|
| Position separate from sort_order | `position` | Already covered by `sort_order` | (no change) |
| HS code / customs | `inventoryItem.harmonizedSystemCode` + `countryCodeOfOrigin` | International shipping compliance | `hs_code` CharField, `origin_country` CharField — defer to a customs plugin |
| Per-variant translations | `translations` | i18n for variant titles | Hook into `localization` plugin (already exists) |
| Multiple media per variant | `media` | Each color variant of a shirt deserves its own gallery | M2M `media` (ProductImage) — REPLACES current `image` FK |
| Bundle components | `productVariantComponents` | "Buy the box: 1 × shirt + 1 × hat" | New `VariantComponent` model — separate plugin |
| Selling plans | `sellingPlanGroups` | Subscriptions, sell-by-weight | The `subscriptions` plugin already exists; just needs variant-level wiring |

### Already-present in Morpheus that Shopify doesn't have

| Morpheus field | What it adds |
|---|---|
| `localized_prices` JSONField | Lightweight per-currency price overrides (Shopify uses Markets; both work) |
| `cost_price` (Money) | Same as Shopify's `inventoryItem.unitCost` |
| `attribute_values` M2M | Closer to Shopify's option/value pair tables, fully flexible |

## 4. Recommended rollout

### Phase 1 — Tier 1 fields (this PR)

**Goal:** every variant can be flagged as `physical`, `digital`, or
`virtual`, with the matching shipping + tax behaviour.

Files to touch:

- `plugins/installed/catalog/models.py:ProductVariant` — add the six
  fields from the Tier 1 table above. Make sure each has a sensible
  default so existing data migrates cleanly.
- New migration: `python manage.py makemigrations catalog -n variant_shopify_parity`
  (the repo hook blocks manual migration writes; this MUST run via
  `makemigrations`).
- `plugins/installed/admin_dashboard/forms.py:VariantForm` — extend
  the form to surface the new fields. Hide `digital_file` when
  `variant_type != 'digital'` via the existing `data-pt-show` pattern
  used on the Product page.
- `plugins/installed/admin_dashboard/templates/admin_dashboard/variant_form.html` —
  add UI for the new fields. Keep it compact; collapse advanced bits
  (barcode, HS code) behind a `<details>`.
- `plugins/installed/orders/services.py` (cart + checkout) — when ALL
  cart items are variants with `requires_shipping=False`, skip the
  shipping-address step. Currently the cart assumes everything ships.
- `plugins/installed/catalog/graphql/types.py:VariantType` — expose
  the new fields so external agents can read + write them.
- `plugins/installed/catalog/services.py` — extend
  `update_product` / `create_product` to accept variant payloads
  with the new fields (currently variants are managed outside the
  shared service).

Acceptance:

1. Create a product with two variants: "Paperback" (physical) and
   "PDF" (digital).
2. The digital variant's row on the storefront PDP omits "Ships
   from…" and "Estimated delivery" widgets.
3. Adding the digital variant to cart, then proceeding to checkout,
   skips the shipping-address step.
4. The merchant's order list shows the digital variant with a
   "Digital — no shipping" pill.
5. Inventory tracking on the digital variant is off by default
   (`inventory_policy='continue'` — never out of stock).

### Phase 2 — variant media gallery (separate PR)

Convert `ProductVariant.image` (FK) to a M2M `media` relation. This
is a destructive migration (FK → M2M) — needs a data migration to
copy existing image refs over.

### Phase 3 — bundle components

New model `VariantComponent` with `variant` (FK), `component_variant`
(FK), `quantity`. Hooks into checkout's reservation + shipping
calculation. Separate plugin (`bundles`).

### Phase 4 — variant translations

Extend the `localization` plugin to track translated `name` per
variant. The model already supports per-variant data; this is mostly
a UI pass.

## 5. Architectural decision — InventoryItem split?

**Shopify's choice:** every variant has a 1:1 `InventoryItem` record
that owns shipping, tracking, customs, and inventory-level data.
This lets the same physical SKU (the InventoryItem) be sold under
multiple variant titles (the ProductVariants).

**Morpheus' current choice:** these fields live directly on the
variant. Simpler model. The trade-off is that you can't share an
InventoryItem across variants (e.g. selling the same shirt as
"V-neck" and "Crew neck" sharing one physical SKU).

**Recommendation:** stay flat for now. The InventoryItem split is
necessary only for the multi-listing case which is < 5% of small/
mid merchants. If we hit that scale, do the split as Phase 5 —
it's a 1-week migration not a 1-day one.

## 6. Risk + rollout

- **Existing variants** all default to `variant_type='physical'`,
  `requires_shipping=True`, `is_taxable=True`,
  `inventory_policy='deny'` — exact same behaviour as today. No data
  migration risk.
- **Checkout shipping skip** is the biggest behaviour change.
  Feature-flag the "all-digital cart skips shipping" path via
  `PluginConfig['orders']['skip_shipping_for_digital_carts']`
  (default ON for new installs; OFF for existing so merchants opt
  in).
- **GraphQL mutation surface** gets new optional fields. Existing
  callers ignoring them work unchanged.

## 7. Out of scope

- Multi-warehouse / multi-location inventory per variant — already
  modelled via `inventory.StockLevel`.
- Variant-level selling plans (subscriptions) — already partially
  modelled in the `subscriptions` plugin; needs separate work.
- Real-time inventory sync to upstream systems (NetSuite / SAP) —
  that's a separate integration plane.

## Sources

- [Shopify ProductVariant GraphQL Admin API](https://shopify.dev/docs/api/admin-graphql/latest/objects/ProductVariant)
- [Shopify InventoryItem (now owns requiresShipping)](https://shopify.dev/docs/api/admin-graphql/latest/objects/InventoryItem)
- [ProductVariantInventoryPolicy enum (DENY / CONTINUE)](https://shopify.dev/docs/api/admin-graphql/latest/enums/ProductVariantInventoryPolicy)
- [Changelog: requiresShipping moved off ProductVariant](https://shopify.dev/changelog/the-inventoryitem-resource-now-indicates-whether-it-requires-shipping-instead-of-the-product-variant)
