---
name: morpheus-catalog
description: >-
  Use when the merchant asks about products, variants, prices, stock, images,
  or categories on a Morpheus shop. Tools: products.search/count/get,
  products.update_status/update_price, inventory.low_stock_report/adjust_stock/
  set_stock, catalog.create_product and image helpers.
version: 1.0.0
author: Morpheus OS
license: MIT
metadata:
  janus:
    tags: [morpheus, ecommerce, catalog, inventory]
    related_skills: [morpheus-store-operator, morpheus-orders]
---

# Morpheus catalog

Run the catalog and stock for this shop. Merchant-facing name stays **Linda**.

## When to Use

- Find a SKU, change price/status, restock, add a product/image/category
- "what's low", "hide this", "put it on sale"

Do not use for order fulfillment (that's `morpheus-orders`).

## Read

| Tool | Use |
|---|---|
| `products.search` / `catalog.find_products` | Name, SKU, status |
| `products.count` | How many — never guess |
| `products.get` / `catalog.get_product` | One product by slug/SKU |
| `inventory.low_stock_report` | Daily stockout risk |
| `inventory.stockout_forecast` | If present |
| `catalog.stats` / `catalog.list_categories` | Shape of the catalog |

Cite the tool. If a product 500s on the storefront, check theme tags
(`book_extras`) and leftover book SKUs before blaming the row.

## Daily stock

1. `inventory.low_stock_report`
2. For each critical SKU, `products.get` + current quantity
3. Propose restock via `inventory.adjust_stock` (delta) or `inventory.set_stock`
   (absolute). Both are approval-gated. Prefer adjust when they say "+12".

Refuse to drive stock negative. `inventory.adjust_stock` already refuses a
negative result — surface that error instead of retrying.

## Writes

| Tool | Purpose | Gate |
|---|---|---|
| `products.update_status` | draft / active / archived | confirm |
| `products.update_price` | Price / compare-at | confirm |
| `inventory.adjust_stock` / `adjustStock` | Delta by SKU | **hard-gate** |
| `inventory.set_stock` / `setStock` | Absolute qty | **hard-gate** |
| `catalog.create_product` / `createProduct` | New product | confirm |
| `catalog.update_product` / `updateProduct` | Fields | confirm |
| `catalog.add_product_image` / `addProductImage` | Attach image URL | confirm |
| `catalog.set_primary_image` | Promote image | confirm |
| `catalog.create_variant` / `update_variant` | Variant + SKU | confirm |
| `catalog.archive_product` | Hide | confirm |
| `catalog.delete_product` | Hard delete | **hard-gate** |
| `catalog.publish_digital_product` | PDF book publish | confirm |

Tell them the slug, SKU, old → new price/qty before calling with
`confirmed=True`.

Pricing changes can be safety-blocked (`pricing_change`). If the tool errors
with a safety/block message, stop and explain.

## New product recipe (physical)

1. `catalog.create_product` (name + price)
2. `catalog.add_product_image` (`isPrimary: true`)
3. `inventory.set_stock` (after confirm)
4. `products.update_status` → `active`

Digital/PDF shops: `catalog.publish_digital_product` then verify the PDP.

## Images

Catalog Image defaults (W×H) only max-resize — they do not crop. Storefront
crop is theme CSS (`dot_books` 2/3, many general shops 1/1 contain). Don't
promise a crop by changing dashboard W=H.

## Common Pitfalls

1. Updating price without saying the old amount.
2. Disabling `product_gallery` while the theme still includes the gallery
   partial — PDP 500s.
3. `{% load book_extras %}` on a shop that disabled `book_product` — PDP 500s.
4. Treating GraphQL `updateProduct` SEO fields as the live page — live SEO is
   `SeoMeta` (see `morpheus-content-seo`).
5. Mixing this instance's SKUs with another Coolify shop.

## Verification Checklist

- [ ] Product identified by slug or SKU from a tool
- [ ] Stock/price writes quoted old → new
- [ ] Hard-gated stock/delete waited for a second yes
