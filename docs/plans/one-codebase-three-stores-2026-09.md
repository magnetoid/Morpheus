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
| `plugins/installed/booking_marketplace/` | 92 | **the only real collision** (below) |
| Other plugins (storefront, seo, marketplace, cms, catalog, affiliates, admin_dashboard, agentic_checkout, referrals, agent_mcp) | ~40 | low — mostly additions, six are generic patches upstream wants |
| `core/hooks.py`, `core/utils/site.py` | 2 | low — both generic |
| `morph/settings.py`, `morph/urls.py` | 2 | low |
| tailwind build, `locale/sr`, docs | ~30 | none |

**No new apps.** Every app Montenegro touched already exists upstream — which is why
this is a merge and not a port.

### The one hard part: `booking_marketplace`

Same app label, two live databases, two incompatible migration histories:

| | models | migrations |
|---|---|---|
| Morpheus | 9 | `0001_initial`, `0002_reconcile_prod_schema` |
| Montenegro | **15** | `0001` … `0014` (incl. a merge migration) |

Montenegro's is a **superset**, not a rival implementation: the same nine models plus a
stays-and-events engine (`Property`, `RoomType`, `StayBooking`, `StayEnquiry`, `Event`).
That is much better than the fork doc feared — but the migration graphs still cannot
simply be merged, because each production database has applied a different one.

There is precedent in this repo for exactly this: `0002_reconcile_prod_schema` already
reconciled a divergent booking_marketplace schema on prod by introspection, idempotently,
with zero SQL by hand (v0.35.1). That is the shape to reuse.

## Plan

Phases 1–3 are safe and independently shippable. Phase 4 is the one that needs a real
Postgres rehearsal against copies of both production databases.

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

### Phase 4 — reconcile `booking_marketplace` (the risky one)

Ship Montenegro's superset models upstream, plus an **idempotent, introspection-driven
reconcile migration** so each database converges from wherever it is:

* dotbooks: gains the five stays/events tables (unused, and its app can leave them empty)
* Montenegro: already has them; the migration must no-op

Non-negotiable: rehearse against restored copies of **both** production databases on real
Postgres. A green sqlite run proves nothing here (CLAUDE.md), and this app has already
503'd production twice through migration divergence.

Open question to settle before starting: whether the stays/events engine belongs in
`booking_marketplace` at all, or should be split into its own app now that it is being
made platform code.

### Phase 5 — cut over

Point the `fo8rvcg94bmcyi43e8iq9tvm` Coolify app at `magnetoid/morpheus`, keeping its
existing `.env` verbatim (`DATABASE_URL`, `MORPHEUS_ACTIVE_THEME=montenegro`,
`STORE_NAME`). Deploy, smoke `/readyz` for the Morpheus version, then smoke the booking,
places and stays paths before declaring it done.

Rollback: point the app back at `magnetoid/montenegro-new` and redeploy — the database is
untouched by the cutover itself, so the old code boots against it as before. **This stops
being true the moment Phase 4's migration runs**, which is why Phase 4 needs a database
backup taken immediately before, and why the nightly backups being broken
(`docs/plans/linda-agent-quality-2026-09.md`) should be fixed first.

### Phase 6 — retire the fork

Archive `magnetoid/montenegro-new` once Montenegro has run on the shared codebase through
a full release cycle.

## Rules this plan must not break

* **No new app may default to enabled.** Anything Montenegro-specific that becomes a
  platform app ships `enabled_by_default = False`, or dotbooks and Supernatural Shop
  silently acquire a feature nobody asked for on their next deploy.
* **Montenegro-specific behaviour arrives as a contribution**, never as an `{% if %}` on
  the store name inside a shared template.
* **One version line.** `MORPHEUS_VERSION` stays the platform version. The fork's
  parallel `v0.39–v0.42` entries meaning different things is exactly the mess that ends
  when there is one repo.
