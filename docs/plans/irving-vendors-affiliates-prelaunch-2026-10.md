# Irving: vendors + affiliates up front, and a real pre-launch (2026-10-10)

Owner's request (2026-10-10): put vendors and affiliates up front, in Irving's
menu and in the dashboard, and give them their pages. Answers to the follow-up
questions:

- **Scope:** both the Irving storefront menu and the dashboard (Vendors and
  Affiliates as their own sections right after Customers, on every store
  running those apps).
- **Indexing:** the beta stays out of search engines until launch, through a
  site-wide switch that is on for Irving only.
- **Pre-launch products:** shown, not sold. The cart and checkout refuse them
  server-side (02f239f only hid the button).

Ownership: the janus-agent-f6 session owns Irving catalogue/editorial content;
this work owns the code (theme nav blocks in `base.html`, SEO, cart rule).

## Steps (each verified before the next)

1. **Cart rule** (orders): config `prelaunch_noindex_not_for_sale`. When on, a
   product marked noindex cannot be added to a cart (`CartService.add_item`)
   and an order cannot be placed with one (`create_from_cart`).
   Verify: tests in `orders/tests/test_prelaunch_products.py`.
2. **Hide until launch** (seo): config `hide_until_launch`. When on, every
   page is `noindex, nofollow` (reason in the head inspector), the sitemap lists
   nothing, and robots.txt names no sitemap. Crawling stays allowed so the
   noindex is seen (a Disallow would freeze already-indexed URLs).
   Verify: tests in `seo/tests/test_hide_until_launch.py`.
3. **Affiliate programme page** (affiliates): public `/affiliates/` with what
   the programme pays and an Apply button. Verify: page test + template compile.
4. **Dashboard sections**: `vendors` and a new `affiliates` section after
   `customers`; affiliates' pages move from `marketing` to `affiliates`.
   Verify: `admin_dashboard/tests/test_navigation.py`.
5. **Irving menu**: Suppliers (`/marketplace/`) and Affiliates (`/affiliates/`)
   in the header, mobile and footer menus, each behind `{% plugin_enabled %}`.
   Verify: theme test renders them, and they vanish when the app is off.
6. Release (MINOR), deploy, switch both settings on for Irving, verify live.
