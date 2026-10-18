---
summary: Delivers a digital product's file to the buyer automatically once their order is paid.
---

## What it's for

This app delivers a product's digital file to the buyer once their order is paid — automatically, with no staff action needed. It emails the buyer a link, and the same links are listed on their account page. A link stops working after it expires or has been downloaded too many times.

## Set it up

Set [](field:digital_products.token_ttl_hours) to control how many hours a download link stays valid, and [](field:digital_products.max_downloads_per_token) to control how many times it can be used, in [Settings](settings:digital_products).

## Good to know

A link is created automatically as soon as an order with a digital product is marked paid, and the buyer is emailed it right away. There is currently no dashboard screen for staff to see which links have been issued or to revoke one — a buyer can always find their own active links on their account's downloads page.
