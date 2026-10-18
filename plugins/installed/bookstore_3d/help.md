---
summary: Adds a 3D, first-person storefront page where shoppers browse real products on virtual shelves.
---

## What it's for

This app adds a "3D store" page, linked from the storefront footer, where a shopper walks through a virtual room and sees real products standing on the shelves. Clicking one opens its normal product page. It is a browsing experience on top of your existing catalogue, not a separate checkout.

## Set it up

In [](settings:bookstore_3d), choose which products to shelve with [](field:bookstore_3d.book_source) — featured, most recent, or one category (its slug goes in [](field:bookstore_3d.source_category)) — and how many to show with [](field:bookstore_3d.max_books), capped at 120. [](field:bookstore_3d.wall_color), [](field:bookstore_3d.floor_color) and [](field:bookstore_3d.accent_color) set the room's colours, and [](field:bookstore_3d.ambient_intensity) sets how bright it looks. [](field:bookstore_3d.enabled) turns the room itself off; the page still exists but shows a short notice instead.

## Common tasks

- Switch which products appear on the shelves between featured, recent or one category.
- Turn the room off for a while without losing your settings or removing the footer link.
- Adjust the room's colours and lighting to match the rest of your store.

## Good to know

Only active products are shelved; the room shows up to 120 of them even if the setting asks for more. Choosing "category" without a valid category slug falls back to showing the most recent products instead. The page needs no sign-in — anyone can open it, and it can be found and indexed like any other storefront page. Turning the room off keeps the footer link and your settings in place; a visitor just sees a notice instead of the scene.
