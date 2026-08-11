# Dashboard & codebase audit — 2026-06

> Goal: a seamless, Shopify-straightforward dashboard. Audit of what's wired /
> working / duplicated / illogical, with a prioritised fix plan. Findings from a
> 4-lens parallel audit (page wiring, settings duplication, layering/invisible
> features, IA/UX). File refs are starting points — re-verify line numbers before
> editing.

## Good news (verified working)
- **All ~60 dashboard pages across 31 plugins resolve** — no missing view
  modules, stubs, or `NotImplementedError`. Defects are grouping/duplication, not
  broken pages.
- **Already-fixed debt:** loyalty `/account/points/` migrated to the `account_nav`
  slot; the legacy `settings_payments()` view/template is gone from admin_dashboard.

## A. Disable-test failures (hardcoded plugin surfaces → 404 when plugin off)
Admin nav (`admin_dashboard/templates/admin_dashboard/base.html`), unguarded by
`{% plugin_enabled %}` (only `affiliates` is guarded):
- `reviews` `/dashboard/reviews/` (~:722-728) · `media` "Assets" `/dashboard/media/` (~:734)
- `tracking` `/dashboard/tracking/` (~:829) · `draft_orders` `/dashboard/draft-orders/` (~:715)
- `notifications_center` `/dashboard/notifications/` + poll (~:897)

Storefront/theme hardcoding owning other plugins' features:
- **Reviews list** — `themes/.../product_detail.html:621` fed by
  `storefront/views/catalog.py:483` (`_published_reviews`). reviews plugin only
  contributes the write-form block → should contribute the list as a StorefrontBlock.
- **Gift-card checkout** — `storefront/views/checkout.py:184,205` + `storefront/urls.py:35-40`
  import `gift_cards.models` → belongs to `gift_cards`.
- **Gift-card/store-credit account tile** — `storefront/views/account.py:344` + `account_home.html:31`.
- **Downloads account tile** — `storefront/views/account.py:384` (digital_products) + `account_home.html:39`.
- **Wishlist account tile** — hardcoded `<a href="/wishlist/">` `account_home.html:44` (404 when wishlist off).
- Clean pattern already exists: `account_home.html:53` `{% storefront_blocks "account_nav" %}` (loyalty uses it).

## B. Duplicated / overlapping settings
- **AI feature flags rendered twice** — `settings.py:671-680` custom cards vs
  `ai_assistant/app.py:~122-138` schema panel (same PluginConfig keys).
- **Dead "Agents" panel** — `settings.py:659-669` renders `settings_panel('agent_core')`
  which is always `None` (agent_core ships no panel). Delete.
- **Service-worker/offline twice** — `settings_caching` PWA block (`settings.py:290-297,460-463`,
  storefront config) vs `pwa/app.py:61,73` (pwa config). Two stores, one toggle.
- **Caching page cross-owns config** — `settings_caching` writes ~25 storefront/seo/cloudflare
  keys from admin_dashboard (`settings.py:262-388`) → ADR 0003 violation; move to owning plugins.
- **GA4 IDs mirrored** — `tracking/app.py:177-178` mirror fields vs `TrackingSettings`
  model at `/dashboard/tracking/` (source of truth). Drop the mirror.
- payments vs advanced_payments: two cards on one page — intentional, not a true dup,
  but the near-identical labels read as duplicate.

## C. Invisible features (shipped, no merchant surface)
`environments`, `experiments`, `functions`, `observability`, `cart_abandonment` —
models/logic but no dashboard/settings UI (only hooks/GraphQL/beat). Either surface
or hide. `inventory` borderline (no dedicated stock page).

## D. IA / UX — too scattered for "Shopify-seamless"
~21 top-level sections today: catalog, customers, orders, payments, sales, marketing,
growth, marketplace, cms, seo, ai, crm, analytics, data, developer, settings, shipping,
taxes, access, plugins, b2b. Problems: overlapping promo rails (marketing/growth/
marketplace); content split (cms/seo, no "Content"); analytics vs data; config pages
(shipping/taxes/access/developer/data) on the main rail instead of the Settings hub;
lonely 1-page sections (b2b/taxes/access); dev clutter (Cloudflare/Metafields/Webhooks/
Workflows/Demo) in the merchant eyeline; no single `SECTION_ORDER` source of truth
(ad-hoc list at `views_split/apps.py:163`).

### Target nav (~9 groups, Shopify-style)
Home · Orders (+Subscriptions, vendor orders) · Products (+Book taxonomies, Dynamic,
Gift cards, Bookvault) · Customers (+CRM) · Marketing (+Affiliates, Marketplace) ·
Discounts (Coupons, Promotions) · Content (CMS pages/blocks/menus/forms/assets + SEO) ·
Analytics · Settings hub (Payments, Shipping, Taxes, Markets, Languages, AI, Notifications,
Caching/Cloudflare, Developer[tokens/webhooks/metafields/workflows], Access, Data, B2B, Plugins).

## Fix plan (phased)
1. **Quick wins (low risk):** guard the 5 hardcoded admin-nav links (or make them
   contributed DashboardPages); move wishlist/downloads/credits/reviews account tiles to
   `account_nav` contributions; delete dead settings code (agent_core card, AI-flag double
   render, GA4 mirror). 
2. **Settings unification:** dedupe SW/offline; move `settings_caching` cross-plugin keys into
   owning plugins; one coherent Settings hub.
3. **IA collapse 21→9:** add a `SECTION_ORDER` single source of truth; remap `section=` across
   plugins; fold config sections into Settings; create Content; merge marketing/growth/marketplace.
4. **Surface or hide invisible features** (experiments/functions/observability/cart_abandonment/environments).

## Status: audit complete (this session). Implementation not started.
