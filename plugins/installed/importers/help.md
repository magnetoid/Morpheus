---
summary: Brings products in from a CSV file or a Shopify store, and exports your products back out.
---

## What it's for
This brings product data into the store two ways: from a CSV spreadsheet, or directly from a Shopify store using an admin API token. It also exports your current products to a CSV file. Running an import again with the same file, or the same shop, does not create duplicates.

## Set it up
Nothing to switch on. For a Shopify move, you will need the shop's name and an admin API token from Shopify, with read access to whichever of products, customers and orders you want to bring over.

## Common tasks
- Upload a CSV file of products to create or update them in [](page:csv).
- Download your current products as a CSV file from the same page.
- Enter a shop name and admin API token to bring products, customers and orders in from Shopify, in [](page:shopify).
- Choose which of products, customers and orders to bring over, using the checkboxes on that page.

## Good to know
The CSV tool here covers products only, not customers or orders. A larger Shopify store — more than a few thousand products — may need a developer to run the move from the server instead of this page, since this page works through the browser and waits for it to finish. Bringing in a WooCommerce store is possible but only from the server's command line today; there is no dashboard page for it yet.
