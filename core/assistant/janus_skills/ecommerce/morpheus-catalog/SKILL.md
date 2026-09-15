---
name: morpheus-catalog
description: >-
  Products, variants, prices, stock, images and categories on a Morpheus store:
  finding a product, what is low on stock, price and status changes, restocking,
  and adding a product.
version: 2.0.0
author: Morpheus OS
license: MIT
metadata:
  janus:
    tags: [morpheus, ecommerce, catalog, inventory]
    related_skills: [morpheus-store-operator, morpheus-orders]
---

# Morpheus catalog

## Read

| Tool | Use |
|---|---|
| `products.search` | By name, SKU or status |
| `products.get` | One product by id, SKU or slug, with variants and stock |
| `products.count` / `catalog.stats` | How many; the shape of the catalogue |
| `catalog.semantic_search` | "Something like…" searches |
| `catalog.list_categories` | Categories |
| `inventory.low_stock_report` | Below a threshold, now |
| `inventory.stockout_forecast` | What will run out soon |

## Stock

1. `inventory.low_stock_report`.
2. Propose `inventory.adjust_stock` for "+12" style changes, or
   `inventory.set_stock` for an absolute count. Stock never goes negative; if the
   tool refuses, report it.

## Changes (each needs the merchant's yes; say old → new)

| Tool | Does |
|---|---|
| `products.update_price` | Price, optionally one variant |
| `catalog.schedule_price_change` | A price that starts later |
| `products.update_status` | Draft, active or archived |
| `catalog.update_product` | Other product fields |
| `catalog.create_product` / `catalog.create_variant` | New product or variant |
| `catalog.add_product_image` / `catalog.set_primary_image` | Images |
| `catalog.archive_product` / `catalog.restore_product` | Hide or bring back |
| `catalog.delete_product` | Permanent — prefer archiving |

## New physical product

1. `catalog.create_product` (name, price).
2. `catalog.add_product_image`.
3. `inventory.set_stock`.
4. `products.update_status` → active.

Digital (PDF) products: `catalog.publish_digital_product`.

## Pitfalls

1. A price change without stating the old price.
2. A price change blocked by a store safety limit: explain it; don't retry.
3. Image size settings resize but never crop; the crop comes from the theme.
