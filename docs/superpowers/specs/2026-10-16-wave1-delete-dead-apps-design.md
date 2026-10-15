# Wave 1: delete the apps and models that do nothing

**Status:** design approved in chat 2026-10-16; spec awaiting owner review.
**Source:** `docs/plans/apps-consolidation-2026-10.md`, Wave 1. The facts below were re-checked on 2026-10-16:
- row counts on all four live stores,
- three read-only reference maps of the tree,
- the Coolify environments of all four stores.

**Ships as:** v0.114.0 ("stop using", MINOR), v0.115.0 ("drop", MINOR), then v0.116.0 ("forget the empty shells", PATCH, may ride with the first Wave 2 change). Wave 2 (merges) is a separate sub-project.

## Goal

Ten apps and thirteen models hold no customer data and do no useful work. Every store still loads
them, and some cost work on every request:
- brand_kit runs a query on every template render;
- loyalty's referral handler runs on every order;
- functions checks its table on every price.

Two of them are visible, and both are wrong:
- smart_shipping draws a second, broken shipping-rate list below the one-page checkout form;
- lumina's `/create/` page sends visitors to `lumina.dotbooks.store`, which answers 502.

Remove all of it without breaking a page, a checkout or a boot, and without losing data anyone wants.

## Success criteria

- After v0.115.0, none of their tables exists on any store; after v0.116.0, none of these apps is installed:
  `one_click`, `rich_post_purchase`, `smart_shipping`, `referrals`, `experiments`, `functions`,
  `environments`, `journal`, `brand_kit`, `lumina`.
- None of these models exists either (table or class):
  - `customers.WishList`, `customers.WishListItem`
  - `agent_core.AgentConversation`, `agent_core.AgentMessage`
  - `ai_assistant.PromptTemplate`, `ai_assistant.AIExperiment`, `ai_assistant.DemandForecast`,
    `ai_assistant.AgentMemory`
  - `marketing.Redirect`
  - `observability.ErrorEvent`
  - `morpheus_brain.DailyReport`, with `ReportReference`
  - `loyalty_points.Referral`
- **Cart, checkout and pages keep working through both deploys.**
  - Cart, both checkouts and an order work on every store, during and after each deploy.
  - The one-page checkout shows one shipping-rate list.
  - `/journal/` and its articles still answer 200 on every store that has them.
- **`/create/` on dotbooks redirects to the home page;** no footer anywhere links to it.
- The two sets of rows worth keeping a copy of are saved on tetra (`/root/content-backups`) before they are dropped:
  - dotbooks' 1,360 stale `observability_errorevent` rows,
  - Supernatural's 3 duplicate `journal_post` and `journal_block` rows.
- **The full suite and every CI gate are green at each release.** The gates are:
  - ruff check and format;
  - `manage.py check`;
  - `makemigrations --check`;
  - the migrations job on real Postgres;
  - the three boundary ratchets, whose baselines shrink;
  - `release --check`.

## Facts this design rests on

**Rows (all four stores, 2026-10-16).**
- Every candidate table is empty, with three exceptions:
  - `experiments.Experiment` holds one row per store: the `checkout_flow` draft seeded by `0002`, never started.
  - dotbooks' `observability_errorevent` holds 1,360 stale rows. The live error log is `morph_errors_errorevent`.
  - Supernatural's `journal_post` and `journal_block` hold 3 rows each.
- Supernatural's 3 journal posts duplicate existing `cms.Page` rows (same slug, same title). The live `/journal/` is served from `cms.Page` (`storefront/views/content.py`, `seo:journal_rss`), never from the `journal` app, which has no views.
- `lumina` has no models or tables. It is enabled only on dotbooks, and its `app_url` is unset, so its buttons use the hardcoded `https://lumina.dotbooks.store`.

**Environments.** No store's `MORPHEUS_EXTRA_APPS`, `MORPHEUS_EXTRA_PLUGINS` or `MORPHEUS_DISABLED_APPS` names any of these apps.

**Hot-path users of the doomed tables.** Old code that queries these tables keeps running in the old containers during a deploy:
- `brand_kit`'s context processor runs on every render;
- `functions` runs on `PRODUCT_CALCULATE_PRICE` and `CART_CALCULATE_BREAKDOWN`, cached for 5 minutes;
- `loyalty_points.handlers.on_order_placed_for_referrals` runs on every `ORDER_PLACED`;
- `experiments` subscribes to `ORDER_PLACED` and `CUSTOMER_REGISTERED`.

A query against a dropped table inside an order's transaction aborts that transaction on Postgres. So no release may drop a table that the previous release still reads.

## Design: expand, then contract, then forget

### v0.114.0: stop using

Afterwards nothing reads or writes these tables. The model classes and tables stay, so the old
containers keep working during the deploy.

**1. The nine apps with tables become model-only shells.**
- **Affected apps:** `one_click`, `rich_post_purchase`, `smart_shipping`, `referrals`, `experiments`,
  `functions`, `environments`, `journal`, `brand_kit`.
- **What each loses:** every surface, i.e. storefront blocks, settings panels, dashboard pages and cards,
  hook subscriptions, context processors, template tags and libraries, middleware, GraphQL extensions,
  views, URLs, templates, services and their tests.
- **What each keeps:**
  - `apps.py`;
  - an `app.py` manifest that contributes nothing;
  - `models.py`;
  - `migrations/`.
- **Each shell's manifest says so in its description:** "Retired in v0.114.0; its tables are dropped in v0.115.0 and the app is removed in v0.116.0."

**2. lumina is deleted outright.**
- It has no tables, so nothing waits for v0.115.0.
- Its directory and its `MORPHEUS_DEFAULT_APPS` entry go.
- Its CMS hardcoded-page row goes with it, because it was a contribution.
- `design/lumina-landing.html` is a mock-up and stays.
- **After deploy (ops):** an `seo.Redirect` from `/create/` to `/` is created on dotbooks. It is created as a row through the dashboard's model, so the redirect cache is invalidated.

**3. References outside the apps are fixed in the same release.**
- **Themes:** `{% load experiments %}` is removed from the `cart.html` of dot_books, irving_survival and supernatural_shop. `{% variant %}` is used nowhere.
- **`dynamics/autopilot.py`:** `_experiment_drafts()` and its call are deleted. The `dynamics → experiments` pair leaves `scripts/plugin_boundary_baseline.json`. The `'winning_strategy'` choice in dynamics stays, since it is model data.
- **The `morph_visitor` attribution plumbing goes**; only `experiments` read it, and nothing has ever set the cookie in production:
  - the cookie reads in `orders/graphql/mutations.py` and `agentic_checkout/views.py`;
  - `create_from_cart(visitor_id=…)`;
  - the `visitor_id` stamp in `_order_metadata`;
  - its test.

  `_order_metadata` itself stays: it carries `consent`, the extra charge lines and store credit. pwa's `PushSubscription.visitor_id` column and its cookie read are left alone, because they are harmless and outside this wave.
- **`api/graphql_permissions.py`:** the `read:functions`, `write:functions` and `read:environments` scope mappings go. These removed GraphQL surfaces are breaking changes:
  - `functions(target)`;
  - `testRunFunction`;
  - `currentEnvironment`, `environments`, `deployments`.

  They are recorded in `docs/MIGRATING.md` and the "Breaking changes shipped" table of `docs/API_STABILITY.md`.
- **Tests:**
  - `admin_dashboard/tests/test_contribution_taxonomy.py` drops `one_click` (payments panels) and `journal` (storefront settings).
  - `core/tests/test_slot_parity.py` drops `journal` from `_INTENTIONALLY_UNRENDERED`.
  - `core/tests/test_slot_render_live.py` is retargeted from brand_kit's tokens to `storefront/blocks/csrf_refresh.html`, another `global_head` contributor that stays.
  - `storefront/tests/test_no_session_for_visitors.py`'s environments assertion stays. It still holds, and it guards the v0.113.0 removal.
- **`scripts/plugin_standard_baseline.json`:** a deleted app's entries go when its code goes. `experiments`, `one_click`, `referrals`, `rich_post_purchase`, `smart_shipping` and `journal` have entries today. The script fails on a stale entry, so `--save` runs in the same commit.

**4. Dead models in kept apps lose their callers** (the classes stay until v0.115.0).
- **`agent_core`:**
  - The conversation path in `services.run_agent` and `history_for_conversation` goes.
  - The `conversation_id` plumbing in `views.py` goes.
  - The `conversationId` GraphQL input field stays and is ignored, so the public schema does not change. Its description says so.
- **`loyalty_points`:**
  - `handlers.py` goes;
  - `services_referrals.py` goes;
  - the `ORDER_PLACED` registration in `apps.py` goes;
  - `tests/test_referrals.py` goes.
- **`morpheus_brain`:**
  - The "Daily Reports" tab and panel go: the template, `views.py`, the `reports` slice in `app.py:on_brain_signals`, and the dead `services.generate_daily_reports`.
  - `core/brain/signals.py` stops seeding `reports`.
  - `tests/test_brain_signals_filter.py` drops its `reports` assertions.
- **`observability`:** `core/errors/tests/test_capture.py:ObservabilityShimTests` and the shim `observability/services.record_error` go. The Audit log page stays.
- **Nothing to change:** `customers.WishList*`, `ai_assistant.PromptTemplate`, `AIExperiment`, `DemandForecast`, `AgentMemory` and `marketing.Redirect` already have no callers.

**5. Docs.**
- README app rows and counts.
- `CLAUDE.md`:
  - the brand_kit and journal examples;
  - the smart_shipping history line stays.
- The SKILLS.md sections and ARCHITECTURE.md lines for functions and environments.
- `docs/PLUGIN_DEVELOPMENT.md`'s stale environments-middleware line.
- The consolidation plan's Wave 1 status.
- `docs/RELEASE_NOTES.md` via `manage.py release --minor`.

### v0.115.0: drop

It deploys only after v0.114.0 serves on all four stores, so the old containers during this deploy
never read these tables.

**1. Backups (ops, before the push).** These go to `/root/content-backups/wave1-2026-10/` on tetra:
- `pg_dump --data-only` of dotbooks' `observability_errorevent`;
- `pg_dump --data-only` of Supernatural's `journal_post` and `journal_block`.

**2. Dead models in kept apps.** The classes are deleted, with one generated migration per app:
- **`customers`:** `DeleteModel` WishListItem, then WishList.
- **`agent_core`:** `DeleteModel` AgentMessage, then AgentConversation.
- **`ai_assistant`:**
  1. `DeleteModel` AIExperiment;
  2. `RemoveField` `AIInteraction.prompt_template`, an always-NULL column;
  3. `DeleteModel` PromptTemplate;
  4. `DeleteModel` DemandForecast;
  5. `DeleteModel` AgentMemory.
- **`marketing`:** `DeleteModel` Redirect.
- **`observability`:** `DeleteModel` ErrorEvent. The app keeps its Audit log page, and `has_models` becomes False.
- **`morpheus_brain`:** `DeleteModel` ReportReference, then DailyReport.
- **`loyalty_points`:** `DeleteModel` Referral.

**3. The nine shells drop their own tables.**
- Each shell's model classes are deleted, and `makemigrations` generates the shell's own `DeleteModel`
  migration while the shell is still installed. Django drops the tables; no hand-written SQL.
  - **Why not drop them from a separate migration once the apps are gone:** the repo's pre-commit safety
    boundary (`check_forbidden_diff`) refuses destructive raw SQL in any committed diff. An uninstalled
    app cannot run its own `DeleteModel`, so the shells stay installed for exactly this.
- The shells, now empty (no models, no surfaces, no tables), stay in `MORPHEUS_DEFAULT_APPS` for one more
  release.
- CI's `migrations` job applies every `DeleteModel` on real Postgres before the deploy.

### v0.116.0: forget the shells

v0.116.0 is a PATCH (`release --patch`) and may ship together with the first Wave 2 change; it carries
no data change.
- The nine empty shells leave `MORPHEUS_DEFAULT_APPS` and their directories are deleted.
- One migration in the `plugins` app (the app registry's own app, always installed),
  `0002_forget_wave1_apps`, removes what Django keeps about an uninstalled app, through the ORM only.
  For each retired label it removes:
  - its `django_migrations` rows (`MigrationRecorder.Migration`);
  - its `ContentType` rows, whose permissions cascade;
  - its `PluginConfig` row.

  It is a `RunPython` with a no-op reverse. **Why the `plugins` app:** core must not know about apps,
  and the registry's own app retiring an app is that app's concern.
- **Remaining references go:** baselines, README counts, `.torsor/map` index files (regenerated), and the
  shells' entries in `_test_settings_tmp.py` (a tracked stray file).

## Left out

- pwa's `PushSubscription.visitor_id` column and its `morph_visitor` read. It is dead but harmless, and the pwa merge is Wave 2.
- `agent_core.AgentMemoryRecord`. The reference map found no reader either, but it is not on the Wave 1 list. It is noted for Wave 2's AI merge.
- Recreating the Lumina landing page as a CMS page. Its target app answers 502; the redirect is enough until Lumina is back.

## Testing

**v0.114.0** (each with a test that fails before its change):
- The cart page renders on all three themes without the experiments library.
- The one-page checkout has one `shipping_rate` radio group.
- No `global_head` output carries `morpheus-brand-tokens`.
- An order placed with the referral handler gone still works.
- The Brain page renders without the Daily Reports tab.
- `create_from_cart` has no `visitor_id` parameter.
- An `invokeAgent` with a `conversationId` still answers.
- No retired app contributes anything (a registry scan over the nine names, kept until v0.116.0).

**v0.115.0 and v0.116.0:**
- The retired apps are not installed.
- After v0.115.0 the shells have no models; their `DeleteModel` migrations run on Postgres in CI's migrations job.
- After v0.116.0, `plugins/0002` leaves none of their migration rows, content types or config rows (tested on sqlite; runs on Postgres in CI).
- `makemigrations --check` is clean.

**After each deploy (live):**
- On every store:
  - `/`, `/cart/`, the checkout pages and `/journal/` answer 200;
  - `/readyz` reports the new version;
  - the error log is clean;
  - the nightly health check (`core/errors/health.py`) is run once by hand and passes. It prices a cart inside a rolled-back transaction; no real order is placed, because ORDER_PLACED subscribers push purchases to GA4 and the ad platforms.
- On dotbooks, `/create/` returns a 301 to `/`.
- After v0.115.0: the retired tables are gone on each store (a `pg_tables` check).
