# One codebase, three stores — folding Montenegro back into Morpheus

Status: **analysis done, execution not started.** Owner asked (2026-09-17) to merge
Montenegro's theme and features into Morpheus and connect it "so that montenegro don't
get broken" — each store keeping its own database, its own enabled apps, and its own
settings.

Supersedes the fork-maintenance approach in `montenegro-new:docs/plans/fork-sync-strategy.md`,
whose analysis this plan reuses and whose measurements it confirms.

## Where we are

| Coolify app | uuid | repo today | version | theme |
|---|---|---|---|---|
| Morpheus (dotbooks.store) | `ghtnqf6lw2bg5229lv1sf4h9` | `magnetoid/morpheus` | v0.68.5 | dot_books |
| Supernatural Shop | `z10xg4j7yq8x1htipw12a368` | `magnetoid/morpheus` | v0.68.5 | supernatural_shop |
| Montenegro Experience | `fo8rvcg94bmcyi43e8iq9tvm` | **`magnetoid/montenegro-new`** | **v0.57.1** | montenegro |

Auto-deploy is enabled and working on all three. Montenegro simply points at a different
repository, last synced from Morpheus on 2026-08-21 at v0.57.0 — 56 commits and ~23
releases ago. There is no sync automation.

## What per-store isolation already exists (verified, not assumed)

Nothing here needs building — the platform already separates these:

* **Database** — each app has its own `DATABASE_URL`. Untouched by this plan.
* **Enabled apps** — `PluginConfig` rows, per database. dotbooks has 112 rows (4 off:
  ai_stylist, importers, staff_sso, store_bootstrap); Montenegro has 109 (2 off:
  agentic_checkout, staff_sso).
* **Theme** — `MORPHEUS_ACTIVE_THEME` env var (`morph/settings.py:36`), default
  `dot_books`. Montenegro's container already sets `montenegro`.
* **Settings** — `StoreSettings` + per-app `PluginConfig.config`, per database.

So a shared codebase changes none of it. The work is code convergence only.

## What actually diverges

One commit (`4704212e`) carries the whole fork: 272 files, +36,590/−753.

| Area | Files | Conflict risk |
|---|---|---|
| `themes/library/montenegro/` | 104 | **none** — upstream has no such directory |
| `plugins/installed/booking_marketplace/` | 92 | none once it becomes Montenegro-only (below) |
| Other plugins (storefront, seo, marketplace, cms, catalog, affiliates, admin_dashboard, agentic_checkout, referrals, agent_mcp) | ~40 | low — mostly additions, six are generic patches upstream wants |
| `core/hooks.py`, `core/utils/site.py` | 2 | low — both generic |
| `morph/settings.py`, `morph/urls.py` | 2 | low |
| tailwind build, `locale/sr`, docs | ~30 | none |

**No new apps.** Every app Montenegro touched already exists upstream — which is why
this is a merge and not a port.

### `booking_marketplace` is Montenegro's product, not a shared app

The owner settled this (2026-09-18): the booking marketplace was built **for Montenegro
Experience**; the other two stores are not meant to have it. The vendor marketplace that
dot_books uses is the separate `marketplace` app. The live row counts agree:

| app | dotbooks | Montenegro |
|---|---|---|
| `marketplace` (vendor: `VendorOrder`, `VendorPayoutAccount`) | **3 rows — in use** | 0 |
| `booking_marketplace` | **0 rows — empty shell** | **1,263 rows** (142 services, 100 properties, 288 room types, 559 reviews, 26 places, 12 events, 15 bookings) |

**So there is nothing to reconcile.** Montenegro's version — a superset: the same nine
models plus the stays/events engine, and 12 template tags to upstream's 5 — becomes the
canonical one, and the stores that never used it stop installing it. No migration runs
against any live database, so the data risk that dominated the earlier draft is gone.

dotbooks does still *serve* four routes from it — `/shop/`, `/places/`, `/bookings/`,
`/regions/` all return 200 — but on zero data, so they are empty shells. Nothing on the
homepage links to `/shop/`, and it appears zero times in the sitemap.

## How the shops should differ (measured 2026-09-18)

Both stores install **109 apps**. The only structural difference is `janus`, which
dotbooks has because Montenegro is still on v0.57.1. Everything else is identical code
running against different data — which is the good news, and also the problem: almost
nothing distinguishes a bookshop from a travel marketplace except which tables happen to
be full.

Counting rows per app across both live databases, and separating apps that own models
from apps that are pure behaviour (where a row count means nothing):

| Class | Count | What it is |
|---|---|---|
| Behaviour-only, no models | 27 | shared platform: storefront, admin_dashboard, agent_mcp, checkout_experience, tax rules, … |
| Data in **both** stores | 18 | the genuine commerce core: catalog, orders-adjacent, customers, payments, seo, cms, analytics, crm, ai_assistant, … |
| Data **only on dotbooks** | 21 | the book vertical (`book_product` 2,574 rows, `audiobooks`) **plus** platform apps that simply have activity there (`observability`, `notifications_center`, `metafields`, `orders`) |
| Data **only on Montenegro** | 1 | `booking_marketplace` (1,263 rows) |
| Models but **no data in either** | 42 | every shop carries their tables and migrations; no shop has ever used them |

**Root cause: only 3 of 111 apps ship `enabled_by_default = False`** (agentic_checkout,
booking_marketplace, staff_sso). The other 108 switch themselves on for any new store, so
a fresh shop inherits 42 apps' tables it will never fill, and a travel marketplace
installs the book vertical.

### The three-tier split to adopt

1. **Platform core** — in `MORPHEUS_DEFAULT_APPS`, on everywhere. The 27 behaviour-only
   apps plus the 18 with data in both stores.
2. **Vertical apps** — *removed* from `MORPHEUS_DEFAULT_APPS` and added per shop through
   `MORPHEUS_EXTRA_APPS`, so their tables only exist where the vertical does:
   * travel → `booking_marketplace` (Montenegro)
   * books → `book_product`, `audiobooks`, `bookvault`, `bookstore_3d`, `flipbook` (dotbooks)
3. **Optional features** — installed everywhere but `enabled_by_default = False`, so the
   merchant turns them on from Settings → Apps: loyalty_points, subscriptions, b2b, drops,
   lookbook, referrals and the rest of the 42.

Tier 3 is **safe for the three existing stores**: `enabled_by_default` is only consulted
when a store has no `PluginConfig` row yet, and all three have rows for everything. It
changes nothing today and stops the next shop inheriting the whole catalogue.

### What stays per-shop, and where it lives

| Concern | Mechanism | Lives in |
|---|---|---|
| Data | `DATABASE_URL` | environment |
| Theme | `MORPHEUS_ACTIVE_THEME` | environment |
| Which vertical apps | `MORPHEUS_EXTRA_APPS` | environment |
| Feature on/off | `PluginConfig.is_enabled` | database (Settings → Apps) |
| Settings, keys, copy | `PluginConfig.config`, `StoreSettings` | database |
| Version | `MORPHEUS_VERSION` | code — one line for all shops |

**The single rule that makes continuous updates work: no shop-specific branch in shared
code.** No `if store_name == …`, no shop's marketing copy inside a shared view. A shop
differs by environment and database, or it differs by having its own app or theme —
never by an edit to a file another shop also runs. Montenegro's fork breaks this today
(its page copy sits inside `storefront/views/content.py`), which is precisely why its
syncs conflict; Phase 3 moves that copy into its theme.

## Plan

All four phases are safe: none of them migrates a live database. Phase 4 changes only
which apps each deployment installs, so the cutover stays reversible throughout.

### Phase 1 — upstream the generic patches

Six fork patches that are improvements to the platform, not Montenegro features. They
stop being fork patches the moment they land, and those files stop conflicting forever.

* `core/utils/site.py` — `store_name` / `store_slug` / `store_contact_email` /
  `store_logo_url` (de-branding; agent manifests currently hardcode "Morpheus")
* `core/hooks.py` — `AI_FEED_ITEMS` event constant
* `seo/services/ai_feeds.py` — fire it, so an AI feed can carry more than catalog products
* `agent_mcp/*`, `agentic_checkout/well_known.py` — merchant brand, omit contact when unset
* `storefront` — the missing `/do-not-sell/` legal route
* `referrals` — `referrals_count|default:0` bugfix

Verify: existing suites green; `/do-not-sell/` 200 on dotbooks.

### Phase 2 — bring the theme in

Copy `themes/library/montenegro/` (104 files) into Morpheus. Inert unless
`MORPHEUS_ACTIVE_THEME=montenegro`: `themes/test_head_contract.py` only runs against the
*active* theme and skips one that does not declare `head_contract >= 1`.

**Done and measured on branch `feat/montenegro-theme`** — and it proved Phase 2 cannot
ship alone:

* All three themes discover cleanly, `dot_books` stays active, 115 theme + slot-parity +
  storefront tests pass. So the copy is harmless to the other two stores.
* But rendering with the theme **active** on current Morpheus gives
  `/products/`, `/journal/`, `/cart/` → 200 and the **homepage → TemplateSyntaxError**:
  `Invalid block tag 'hero_pills'`.

The theme's homepage loads `{% load booking_tags %}` and calls six tags Morpheus does not
have (`hero_pills`, `booking_categories`, `featured_filters`, `home_categories`,
`home_testimonials`, `booking_enquiry_only`), which in turn call
`booking_marketplace.services.active_categories` and `views.takes_enquiry_only` — neither
of which exists upstream. Morpheus has 5 of Montenegro's 12 booking tags.

**Therefore the theme must land with Phase 3/4, not before.** Shipping it alone would put
a theme in every store's theme picker whose homepage 500s — the platform's own rule is
that a broken surface is worse than an absent one. The branch stays unmerged until the
booking app's tags, services and views come with it.

### Phase 3 — the remaining plugin deltas

Per-file review of the ~40 remaining changed files. Each one is either (a) generic → merge,
or (b) Montenegro-specific → must arrive as a *contribution* (hook, `StorefrontBlock`,
`DashboardPage`) rather than an edit to a shared file, per the plugin contract. Anything
that cannot be expressed as a contribution is called out rather than smuggled in.

### Phase 4 — make `booking_marketplace` a Montenegro-only app

Now that it is one store's product, this needs **no migration on any live database**:

1. Replace Morpheus's 9-model version with Montenegro's 15-model one (models, migrations
   `0001`–`0014`, services, views, the 12 template tags, dashboard, templates).
2. **Remove it from `MORPHEUS_DEFAULT_APPS`.**
3. Montenegro's Coolify environment adds it back with
   `MORPHEUS_EXTRA_APPS=plugins.installed.booking_marketplace`
   (`morph/settings.py:225` — a comma-separated env var merged into `ALL_MORPHEUS_APPS`;
   it also still reads the old `MORPHEUS_EXTRA_PLUGINS` name).

Why this is safe rather than clever:

* **Montenegro's database is untouched.** It has already applied migrations `0001`–`0014`
  under these exact names, so `migrate` is a no-op there.
* **dotbooks' database is untouched.** The app simply leaves `INSTALLED_APPS`; its empty
  tables and its `django_migrations` rows stay behind, inert — Django ignores migration
  rows for apps it no longer installs. Optional cleanup later, not a prerequisite.
* **Nothing imports it.** `grep` across `core/`, `plugins/installed/`, `themes/` and
  `api/` finds no importer outside the app itself, so removing it from the default set
  cannot break a sibling.

Two loose ends to handle in the same change:

* dotbooks loses `/shop/`, `/places/`, `/bookings/`, `/regions/`. Nothing links to them
  and they carry no data, but `/shop/` has been crawled — add `seo` `Redirect` rows
  (`/shop/` → `/products/`) as **data**, not code.
* The theme picker would still offer `montenegro` on a store without the app, where its
  homepage would fail on `{% load booking_tags %}`. Gate the theme on the app being
  installed, or the picker is a trap.

Verify: Montenegro boots with the env var and its booking pages still serve real data;
dotbooks boots without the app and every other route is unchanged.

### Phase 5 — cut over

Point the `fo8rvcg94bmcyi43e8iq9tvm` Coolify app at `magnetoid/morpheus`, keeping its
existing `.env` verbatim (`DATABASE_URL`, `MORPHEUS_ACTIVE_THEME=montenegro`,
`STORE_NAME`). Deploy, smoke `/readyz` for the Morpheus version, then smoke the booking,
places and stays paths before declaring it done.

Rollback: point the app back at `magnetoid/montenegro-new` and redeploy. Because Phase 4
runs no migration against either live database, this stays true throughout — the old code
boots against the same data as before. That is the single biggest reason to prefer the
extra-apps approach over schema reconciliation.

### Phase 6 — retire the fork

Archive `magnetoid/montenegro-new` once Montenegro has run on the shared codebase through
a full release cycle.

## Rules this plan must not break

* **A store-specific app is not in `MORPHEUS_DEFAULT_APPS` at all.** Per-store app sets
  belong in the deployment environment (`MORPHEUS_EXTRA_APPS`), not in a shared code
  list — otherwise every store installs, migrates and routes an app it will never use.
  `booking_marketplace` on dotbooks is exactly that mistake already shipped: an empty
  app serving four dead public URLs on a bookshop.
* **Montenegro-specific behaviour arrives as a contribution**, never as an `{% if %}` on
  the store name inside a shared template.
* **One version line.** `MORPHEUS_VERSION` stays the platform version. The fork's
  parallel `v0.39–v0.42` entries meaning different things is exactly the mess that ends
  when there is one repo.
