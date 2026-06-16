---
type: progress
status: active
tags:
- active
links: []
created: '2026-06-13T00:48:59'
updated: '2026-06-13T00:48:59'
---

# Progress

Shipped this session (all on main, deployed, verified live): (1) Two P1 prod 503s fixed — PR #62 enabled 11 roadmap plugins with fields.E301/E300/E307 model errors (auth.User FKs not swapped to customers.Customer; ugc_reviews.ReviewMedia→non-existent reviews.Review; returns_portal.ReturnItem→non-existent orders.OrderLine) → repaired + regenerated migrations + re-enabled; PR #64 returns_portal consolidation onto orders.ReturnRequest crashed migrate with bigint→uuid AlterField cast → fixed 0002 to RemoveField+AddField (tables verified empty) + re-enabled. (2) Predictive Stockout Alerts inventory feature: StockoutAlert model (partial unique constraint dedup), sync_stockout_alerts reconciler, daily beat task + notify_all_staff (newly-opened only), inventory.stockout_forecast agent tool, Stockout Forecast dashboard page; ALSO fixed the never-functional forecast_all() engine (Sum('available_quantity') non-field + Sum('quantity') vs quantity_change) and a webhooks_ui lazy-query fanout bug; 16 tests. (3) Storefront cleanup: single Add-to-cart CTA (removed Quick view + orphaned modal), removed roadmap-plugin home-page clutter (lookbook/discovery_quiz/drops/rails home blocks). (4) Journal: clarified journal articles are CMS pages at /journal/{slug}/ edited via cms page_form (the dedicated `journal` plugin is a PR#62 stub); added a cover-image Upload button posting to /dashboard/media/api/upload/ (lands in central Media library) and fixed the cover input type=url→type=text so relative /media/ URLs save. (5) CI gates: blocking `manage.py check` (concurrent session fixed the `|| true`), new Postgres migrate gate (concurrent session added sslmode=disable). (6) Deleted all 7 merged claude/* remote branches — only main remains.
