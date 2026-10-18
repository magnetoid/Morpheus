---
summary: Adds a recently-viewed rail, featured-collection rails and a low-stock badge to the storefront.
---

## What it's for

This app adds three small storefront features on top of your catalogue. The home page can show a slider for each collection you mark as featured, plus a "recently viewed" rail built from what each shopper looked at. A product's own page can show a badge such as "Only 2 left" once its stock falls below a cutoff you choose.

## Set it up

In [](settings:advanced_ecommerce) you can turn the featured-collection rails on or off with [](field:advanced_ecommerce.enable_collection_rails), and set how many products show in each rail ([](field:advanced_ecommerce.collection_rail_products)) and how many rails the home page shows ([](field:advanced_ecommerce.max_collection_rails)). [](field:advanced_ecommerce.low_stock_threshold) sets the cutoff for the "low stock" badge; the same number is also used by the low-stock list on the dashboard home page.

## Common tasks

- Mark a collection as featured from [](section:products) to add it as a homepage rail.
- Change the low-stock cutoff so the badge matches how often you restock.
- Turn collection rails off if you would rather the home page ended at the product grid.

## Good to know

A shopper's recently-viewed list is kept on their own visit only; it is never saved to their account, and search engines and other crawlers never get one. Collections with no products, or that are not marked featured, never appear as a rail. This app has no dashboard page of its own — its settings live in [](settings:advanced_ecommerce).
