# Platform, admin, identity, content, AI and vertical apps: audit

Scope: 37 apps plus `observability`, checked against `core/`. Row counts are listed per store (dotbooks / supernatural / montenegro / irving). "Real" means it does what it says today, "thin" means it works but adds little, and "stub" means the manifest promises things the code doesn't do.

## Per-app table

| App | What it really does today | Real/stub | Verdict | Key improvements |
|---|---|---|---|---|
| admin_dashboard | The dashboard shell: navigation hubs, settings-panel renderer, apps page, home and palette. It also contains the full CRUD for products, categories, collections, orders, customers, coupons and returns (`views_split/products.py` 1119 LOC, `orders.py` 594, `customers.py` 431, plus 54 imports from catalog and 26 from orders). | Real, protected | Keep | Move the domain pages into the apps that own them (catalog, orders, customers, marketing/promotions, cloudflare). The shell should end up with only nav, settings, apps, home and palette. `views_split/settings.py` (1368 LOC) holds the provider catalogue and the settings renderer, so it should be split. |
| storefront | The shopper views (catalog, checkout, account, content, vendor), caching tags and maintenance middleware. It also has its own service worker. | Real, not protected | Keep, and absorb pwa | `views/catalog.py` (1721 LOC) imports book_product 10 times, so the book vertical is welded into the shell; book pages should become book_product contributions. Delete `storefront/sw.py`, which duplicates pwa. Consider protecting the app: disabling it takes the whole shop offline. |
| store_bootstrap | One request turns a sentence into a brand voice, categories and products through a synchronous 10–30 s LLM call (`views.py:55`) on ai_assistant's gateway. | Thin, 0 tests, switched off on dotbooks | Merge into demo_data ("Store setup"), opt-in | Bypasses Janus gates, the kill switch and the spend cap. Turn it into a Janus skill that calls the existing `catalog.create_*` tools. |
| demo_data | Seeds an idempotent bookstore demo (books, genres, vendors, customers, orders) plus random products. | Real, already non-default | Keep as opt-in "Store setup" (absorbs store_bootstrap) | Declares `requires_plugins` (`app.py:16`, not a manifest key) but imports book_product. Should be `requires=['book_product']`, or the book seeding should move into the books vertical. |
| environments | Dev/staging/prod models plus snapshot/promote services. There is no UI. Its middleware sets `request.environment`, and nothing reads it. | Stub, 0 rows | **Delete** | The middleware is hardcoded in `settings.MIDDLEWARE` (`morph/settings.py:362`), so it runs 1–2 DB queries on every request even when the app is off. |
| backups | A Celery beat wrapper and settings panel around core's `morph_backup` command. | Real, thin (81 LOC manifest) | Merge into the "system" app (see release_notes) | Disabling the app silently stops nightly backups. It should sit in a protected app. |
| release_notes | Help and About pages (embedded from morpheus.direct) plus Version & updates (renders RELEASE_NOTES.md). | Real | Keep as host: rename to `system` and absorb backups and feedback | — |
| localization | A read-only list of `core.i18n` Translation rows, a "Languages" page, a footer language switcher and GraphQL access to translations. | Thin, 0 tests | Merge into markets ("Markets & languages"), or keep and fix | The manifest says translations can be edited inline, but the page is read-only (`views.py:18-60`). The Languages page writes `i18n.enabled_languages` while routing reads env `MORPHEUS_LANGUAGES` (`morph/settings.py:620`), so the control does nothing. `requires=['catalog']` is never used. |
| brand_kit | A context processor that emits CSS variables from an active `DesignTokenSet`. There is no UI to create a token set, the `Asset` model is unused, and the AI generator in the manifest doesn't exist. | Stub, 0 rows | **Delete** (or build an editor and a Janus tool) | Queries the DB on every storefront request for a row nobody can create (`context_processors.py:40`). The `active_token_set` setting is not what selects the set (`is_active` is). |
| consent | Cookie banner, `ConsentLog` audit trail, `consent` template context gating pixels and beacon, GPC handling. | Real, 105 rows | Keep as host of the privacy merge | In `core/safety.py` protected paths. No Janus tool; that is correct (consent belongs to the shopper). |
| gdpr | `/account/privacy/` self-service export and erasure, a `DataRequest` trail, seeding of Privacy/Terms/Imprint pages, AI-disclosure copy override. | Real, 0 rows | **Merge into consent** ("Privacy") | Already `requires consent`. The master switch lives in `core.StoreSettings.gdpr_enabled`. |
| rbac | Roles, role bindings and the `AUTHZ_CAPABILITY_CHECK` answerer. 3 tools (grant, revoke, list). | Real, protected, rows 7/6/6/6 (system roles only) | Keep; absorb the audit-log page from observability | **No in-app tests** (only `core/tests/test_authz.py`). `ready()` writes to the DB at every boot (`app.py:33`, `Role.ensure_system_roles()`); move that to a post_migrate signal. |
| staff_mfa | TOTP second factor through `AUTH_SECOND_FACTOR`, recovery codes, break-glass reset. | Real, 1 device per store | Keep; absorb staff_sso → "Staff sign-in" | Deliberately has no agent tool, and must not get one: an agent must never reset MFA. |
| staff_sso | allauth OIDC/SAML for staff with an interposed MFA check (resolves staff_mfa softly through the registry). | Real code, **off on all 4 stores**, 0 rows | **Merge into staff_mfa**, opt-in | The allauth `openid_connect` and `saml` providers sit in INSTALLED_APPS unconditionally (`morph/settings.py:286,292`), so the native deps load at boot even though no store uses SSO. |
| customers | The auth user model (`Customer`), Address, RFM segments with migrations, GDPR hooks. 2 read tools. | Real, protected | Keep | Dead `WishList`/`WishListItem` (`models.py:154,164`, no reader anywhere) duplicate the `wishlist` app. Merchant writes (edit customer, address, tags) have no tool. |
| crm | Leads (fed from hooks), accounts, pipeline and deals, interactions, tasks, mail inbox, support chat, notes. 8 tools. | Real, 2210/82/13/0 rows | Keep | Still ships a specialist `AccountManagerAgent` with a bookstore prompt (`crm/agents.py`), against the one-Worker pivot (`agent_core/agents/__init__.py:3-9`). Customer notes exist twice (see Notable problems). |
| feedback | Staff bug tickets with screenshot, console errors and a snapshot of `core.errors`. | Real code, 0 rows on all stores | **Merge into `system`** (release_notes) | A "Report a problem" page belongs next to Help. |
| cms | Pages with sections, blocks, menus, forms, email templates. Also **the live journal** (Page with `metadata.category='journal'`). 11 tools. | Real, 185/29/57/33 rows | Keep | `seed_publisher_pages` (407 LOC) and `seed_journal_articles` (246 LOC) are dotbooks content in a shared app; move them to a per-store content package. |
| journal | `Post`/`Block` models and a block template for slot `journal`. **No views, no editor, no dashboard.** The slot is never rendered (`core/tests/test_slot_parity.py:39`). | Stub, 6 orphan rows on supernatural | **Delete** (move the 6 posts to cms Pages first, if wanted) | The manifest's "Notion-style block editor" doesn't exist. |
| seo | The head document, JSON-LD, sitemaps, redirects, index rules, templates, audit, 404 log, AI feeds, IndexNow, llms.txt. 11 tools. | Real, largest data, 15.5k LOC | Keep; **don't split the app** (it is one domain with clean `head/ rules/ schema/ pages/ services/` packages) | Split `views.py` (1880 LOC) by area. `TrackedKeyword` has no writer, yet the dashboard reports "keywords in top 10" (`views.py:521`, always 0): wire it up or drop it. Delete the duplicate `marketing.Redirect` (`marketing/models.py:85`, no reader). |
| agent_core | Worker runtime glue: runs/approvals views, 37 tools, automations (cron + `BackgroundAgent`), guardrails settings, AI-Act export. | Real, protected and system | Keep; **host of the AI merge** | 22 `catalog.*` tools, `orders.mark_*` and `inventory.set_stock` duplicate the owner apps' `products.*`/`orders.*`/`inventory.adjust_stock` (two vocabularies). `AgentConversation`/`AgentMessage` have 0 rows on all stores and duplicate `core.assistant` chats. `BackgroundAgent` has 0 rows (automations are unused so far). |
| agent_mcp | MCP servers (storefront/cart/checkout/admin), UCP/well-known, Web Bot Auth, the Linda turn edge, the `janus.ask` door. | Real, 185 tests | Keep; **mark protected** | Janus reaches every store tool through `/mcp/admin/v1/` (`core/assistant/janus_engine.py:525,541`). Disabling this app leaves Linda with zero tools, and it is not in `PROTECTED_PLUGINS` (`core/safety.py:78-91`). |
| ai_assistant | Provider keys (the provider registry), embeddings and semantic search, recommendations, the RAG retriever, Pulse insight cards, a dynamic-pricing hook, "agent intents" GraphQL, **its own 10-class LLM gateway**. | Mixed, 11.7k/1.2k/541/563 rows | Keep but slim (see merge 1b) | Dead models: `PromptTemplate`, `AIExperiment`, `DemandForecast` (no reader); `AgentMemory` is read per request but never written. Three 1-line stub modules (`services/memory.py`, `forecasting.py`, `assembler.py`). Its gateway ignores the kill switch and spend cap. `AIContextMiddleware` writes the session on every visit (see Notable problems). |
| ai_content | A brand-voice config (4 fields) prepended to agent prompts through `AGENT_SYSTEM_PROMPT`. | Thin; config only | **Merge into agent_core** | `services_bulk_catalog.py` (209 LOC) has no importer. The manifest still describes an auto-description-on-create path that was removed. |
| linda_generated | A landing directory for self-authored tools from a pipeline that was removed in v0.65.0. | Stub, empty | **Delete** | Imports nothing; it is boot-time code with no purpose. |
| janus | The Settings → AI → Janus page plus a config schema (core reads it through `janus_settings.py`), and a GitHub check for newer builds. | Real, protected and system | **Merge into agent_core** | `extra_instructions` (standing instructions) overlaps ai_content's brand voice: one prompt-prefix setting is enough. |
| morpheus_brain | The Brain console page and `BrainBriefing` (LLM advisory). `DailyReport` holds **hardcoded "2027 research" text**: `generate_daily_reports()` (`services.py:122`) has no caller, but `on_brain_signals` publishes whatever rows exist. | Real page with fabricated reports; protected; 20 rows on dotbooks | **Merge into `core/brain`** (the engine already lives there) | Delete `DailyReport`/`ReportReference`. Three "proactive AI review" producers overlap: Brain briefing, Linda's daily briefing (`core/assistant/briefing.py`) and Pulse (ai_assistant). |
| pwa | Manifest, `/sw.js`, offline page, push subscribe/unsubscribe. | Real; push half-built | **Merge into storefront** | Push subscriptions are stored (`views.py:141-193`) but nothing ever sends a push. A second `/sw.js` exists in storefront (see Notable problems). |
| book_product | The book vertical: BookProduct, Genre/Topic, taxonomy terms, author/series/format pages, dashboard taxonomy page. | Real, dotbooks only (2574 rows) | **Opt-in**, and host of a "books" bundle | Default on every store; three stores remove it via `MORPHEUS_DISABLED_APPS`. 0 Janus tools (genre/topic assignment, book metadata). |
| audiobooks | Generates audiobooks from book PDFs (TTS), a PDP player and a product-form card. | Real, 7 rows on dotbooks | **Merge into book_product** | Requires book_product already; 0 tools. |
| bookvault | Print-on-demand fulfilment through the Bookvault API (quotes, auto-send, links). | Real code, **0 rows on all stores** (on at dotbooks/montenegro, off at supernatural/irving) | **Opt-in** (out of the defaults); delete if nobody plans to use it | 0 tools; never used. |
| eco_impact | Paper/CO₂ footprint for books, tree-pledge opt-in at checkout. | Real, 0 rows | **Merge into book_product** | A general-sounding app that `requires book_product` and returns None for non-books (the CLAUDE.md anti-pattern). |
| marketplace | Vendor applications, payout accounts, vendor orders (split on `ORDER_PLACED`), payouts, vendor portal. | Real, 3/3/1/0 rows | **Opt-in** | 0 Janus tools for approving vendors or paying out. |
| booking_marketplace | Montenegro travel: services/bookings/enquiries, places, stays (property/room/stay booking), events, host portal, its own SEO and feeds. | Real, already opt-in | Keep; move content out | About 9.7k of its 15k LOC is **store content in management commands** (`_experiences_data.py` 5289, `seed_places.py` 1902, hotels, events, journal, reviews). Move that to a montenegro content package; the code then is about 5.3k LOC and doesn't need splitting. Bookings never touch `orders`/`payments` (no payment leg). **0 Janus tools** for confirming or cancelling bookings or setting availability. |
| catalog | Product, variant, image, category (MPTT), collection, attributes, vendor, Review, PriceSchedule; search backends. | Real, protected | Keep | Take back its pages from admin_dashboard and its tools from agent_core. `catalog.schedule_price_change` lives in inventory (`inventory/agent_tools.py:165`). Search backends import book_product. |
| inventory | Warehouses, stock levels and movements, back-in-stock, stockout alerts, the reservation gate. | Real, rows ~0 (owner runs no stock limits) | Keep | `inventory.set_stock` (agent_core) and `inventory.adjust_stock` (here) are the same concept twice. |
| orders | Cart, Order FSM, items, fulfilment, refunds (RefundService), store credit. 10 tools. | Real, protected | Keep | agent_core's `orders.mark_refunded` bypasses RefundService and the FSM (see Notable problems). |
| observability *(asked)* | The audit-log page, plus a **retired** `ErrorEvent` table and a deprecated `record_error` shim that forwards to `core/errors`. | Thin; 1360 dead rows on dotbooks | **Delete**: audit page → rbac (or core/audit), drop the retired table | The audit model already lives in `core/audit`. |

## Merges

1. **AI app: fold `janus`, `ai_content` and `linda_generated` into `agent_core`** (protected, system).
   - Why: these are four apps for one subsystem. All of it already lives under Settings → AI.
   - What moves: config rows only (PluginConfig `janus` and `ai_content`, 0 model rows). `core/assistant/janus_settings.py` reads the config by the name `janus`, so point it at the new owner and copy the row in a data migration. Fold `extra_instructions` and brand voice into one prompt-prefix setting. `linda_generated` goes away.
   - Risk: low to medium (config keys are coupled by string; check the tests that name the apps).
   - **1b (phase 2):** move ai_assistant's provider-key config (the `ai_providers` panel and `provider_config_registry.register`) into the same protected app. Disabling ai_assistant today drops every dashboard-stored key and Linda breaks. ai_assistant then stays an optional "AI signals" app (embeddings, search, recommendations, RAG, Pulse). Risk: medium, because ~8 callers import `ai_assistant.services.llm`. Do this together with merge 11.
2. **`morpheus_brain` → `core/brain`.**
   - Why: the engine is already core, and the app is in `PROTECTED_PLUGINS` as "a core capability".
   - What moves: `BrainBriefing` (≤20 rows, dotbooks) via `SeparateDatabaseAndState` keeping the table name (the ADR 0034 precedent) and the page view (`core/errors` already serves pages from core). **Delete** `DailyReport`/`ReportReference` (fabricated static text).
   - Risk: medium (a model move with zero SQL).
3. **`gdpr` → `consent`**, renamed "Privacy".
   - Why: gdpr already requires consent; one merchant concept, one switch (`gdpr_enabled`).
   - What moves: `DataRequest` (0 rows, can be regenerated), URLs, legal-page seeding, the AI-disclosure hook. `ConsentLog` (105 rows) stays put. Update the `core/safety.py` protected-path entry if the directory changes.
   - Risk: low.
4. **`staff_sso` → `staff_mfa`**, renamed "Staff sign-in".
   - Why: both interpose on staff sign-in, and SSO must run the MFA gate. Today that is a soft cross-app registry lookup (`staff_sso/adapters.py:193`).
   - What moves: code only (staff_sso has no models). `StaffMfaDevice`/`MfaRecoveryCode` stay.
   - Risk: low. Keep SSO behind a per-provider switch; it is off on every store.
5. **`observability` → audit-log page into `rbac`** ("Team": roles plus who did what). Delete the app and the retired `ErrorEvent` table (1360 dead rows on dotbooks) and the `record_error` shim.
   - Risk: low. Grep for remaining `observability.services.record_error` callers first; only a test imports it today.
6. **`feedback` and `backups` → `release_notes`**, renamed `system` (Help, About, Version & updates, Backups, Report a problem). Mark it protected.
   - Why: all three are platform maintenance, model-less except `FeedbackTicket` (0 rows on all stores).
   - Risk: low. Backups currently stop silently if someone disables that one app.
7. **`pwa` → `storefront`.**
   - Why: two `/sw.js` owners with two toggles (`storefront/urls.py:10`, `pwa/urls.py:13`; `settings_caching.html:256` vs pwa's `enabled`).
   - What moves: `PushSubscription` (0 rows). Delete `storefront/sw.py` and the Caching-page service-worker toggle, keeping pwa's worker.
   - Risk: low. Either finish push sending or drop the push endpoints.
8. **`audiobooks` and `eco_impact` → `book_product`** ("Books" vertical), and **take the bundle out of `MORPHEUS_DEFAULT_APPS`**.
   - What moves: `Audiobook` (7 rows, dotbooks) and `TreePledge` (0 rows), via `SeparateDatabaseAndState` keeping the tables.
   - Risk: medium. Add `book_product` to dotbooks' `MORPHEUS_EXTRA_APPS` in Coolify *before* the deploy that drops it from the defaults, or /genres/, /authors/ and the rest 404 on the live store. Also clean up the 25+ shell imports of book code (storefront `views/catalog.py` ×10, seo ×9, catalog ×3 (context processor and both search backends), orders, shipping, google_shopping, webstories) or gate each one with `is_active`. `bookstore_3d` and `flipbook` (another cluster) belong in the same bundle.
9. **`store_bootstrap` → `demo_data`** ("Store setup", opt-in, non-default).
   - Why: both seed a store, and neither belongs on a live store by default.
   - What moves: code only. Rewrite the bootstrap as a Janus skill over existing catalog tools, so it goes through the gates and the spend cap.
   - Risk: low.
10. **`localization` → `markets`** ("Markets & languages", the Shopify model). This one is optional.
    - What moves: two pages, the switcher block and GraphQL extensions (no models).
    - Risk: low. Fix the dead Languages control at the same time: either drive `LANGUAGES` from it or make the page show the env value read-only.
11. **ai_assistant's agent intents and LLM gateway out.**
    - `AgentIntent`/`AgentIntentEvent`/`AgentRegistration` (an external-agent checkout-intent API) move into `agentic_checkout` or `agent_mcp`, the apps that own agent commerce doors.
    - `services/llm.py` is replaced by `core/agents/llm.py` so there is one provider stack.
    - Risk: medium. Check the intent row counts on dotbooks before moving: ai_assistant's 11.7k rows are mostly `AIInteraction`, embeddings and knowledge chunks.

**Delete outright:** `environments`, `journal`, `linda_generated`, `brand_kit`, and the dead models `customers.WishList(Item)`, `agent_core.AgentConversation/AgentMessage`, `ai_assistant.PromptTemplate/AIExperiment/DemandForecast/AgentMemory`, `marketing.Redirect`, `observability.ErrorEvent`, plus `ai_content/services_bulk_catalog.py`.

**Move out of the default list (opt-in):** book_product (with audiobooks and eco_impact), bookvault, marketplace, demo_data/store_bootstrap, and staff_sso (inside merge 4). booking_marketplace is already opt-in.

Net effect for this cluster: 38 apps → 21 (17 fewer), and the AI subsystem goes from 9 apps to 3 (`agent_core`, `agent_mcp`, `ai_assistant`).

## Notable problems

1. **A refund tool bypasses refunds.** `agent_core/tools/orders.py:190-193` (`orders.mark_refunded`) does `Order.objects.filter(pk=…).update(status='refunded', payment_status='refunded')`. That skips the FSM, `post_save`, `PAYMENT_REFUNDED` (so gift-card and loyalty tenders are never re-credited) and RefundService. Meanwhile `orders.refund` (`orders/agent_tools.py:228-270`) is the correct path. Delete the agent_core tool, or make it call the FSM transition.
2. **Linda's tools can be switched off by accident.** `agent_mcp` is missing from `PROTECTED_PLUGINS` (`core/safety.py:78-91`), yet Janus gets every tool through `/mcp/admin/v1/` (`core/assistant/janus_engine.py:525,541`). Turning it off leaves Linda answering with zero tools.
3. **A second LLM stack runs outside the guardrails.** `ai_assistant/services/llm.py` (10 gateway classes) has no check for `agents_paused` or the spend cap. `core/agents/guardrails.py:96-143` counts only `AgentRun` and Linda's messages, not `AIInteraction`. Callers that escape the kill switch and cap: store_bootstrap, the dashboard AI writers (`admin_dashboard/views_split/_shared.py`), `book_product/services_copy.py`, `seo generate_pdp_faqs`, `catalog populate_descriptions`, and ai_assistant's own tasks. The two stacks have already drifted: Packy is Anthropic-based at `ai_assistant/services/llm.py:439` and OpenAI-based at `core/agents/llm.py:592`, and Moonshot exists only in core.
4. **A session is written on every visit for nothing.** `ai_assistant/middleware.py:116-120` writes `request.session['ab_cohort']` for every visitor that lacks one, crawlers included. That means a session row plus `Set-Cookie` on anonymous storefront responses, and `ab_cohort` is read nowhere. The same middleware queries `AgentMemory` on every authenticated request (`:91-101`), a table nothing writes.
5. **environments adds queries to every request.** Its middleware is hardcoded in `morph/settings.py:362` and runs 1–2 queries per request (`environments/middleware.py:28-35`). It runs even when the app is disabled, and nothing reads `request.environment`.
6. **Two service workers.** `storefront/urls.py:10` (`sw.py`, toggled by the Caching page) and `pwa/urls.py:13` both mount `/sw.js`. pwa wins the route, so storefront's view is dead code. Its Caching-page switch (`service_worker_enabled`) still injects its own register script (`storefront/templatetags/caching.py:99-110`), which then registers pwa's worker. The result is two switches for one worker, and neither tells the merchant which one is in charge.
7. **Fabricated reports in the Brain console.** `morpheus_brain/services.py:122` `generate_daily_reports()` writes hardcoded "2027 trends" articles with references. It has no caller, but `app.py` `on_brain_signals` publishes any `DailyReport` rows as "daily AI reports".
8. **Dead controls:**
   - `localization/views.py:67-79` saves languages that routing never reads (`morph/settings.py:620-627` reads env `MORPHEUS_LANGUAGES`).
   - `brand_kit` has no way to create the `DesignTokenSet` its context processor queries on every request (`brand_kit/context_processors.py:40`).
   - `seo/views.py:521` reports tracked keywords that nothing writes.
9. **Two vocabularies for the same tools.** agent_core registers `catalog.update_product/archive_product/delete_product/...` (22 tools in `agent_core/tools/catalog.py`) next to catalog's `products.update_price/update_status`, and `inventory.set_stock` next to `inventory.adjust_stock`. Tool names are single-owner per CLAUDE.md, but here the *concept* has two owners. Move each into its owner app and keep one name per action.
10. **Customer notes are stored twice.** `customers.add_note` (`core/assistant/tools/ecommerce_writes.py:134`) appends to `Customer.notes`, while crm has a `CustomerNote` model (`crm/models.py:467`) and `crm.log_interaction`. A note written by Linda doesn't appear in the CRM timeline.
11. **A leftover specialist agent.** `crm/agents.py` registers `AccountManagerAgent` with "an independent bookstore" in its prompt, against the single-Worker pivot recorded in `agent_core/agents/__init__.py:3-9`.
12. **Missing Janus tools for merchant actions:**
    - booking_marketplace: confirm or cancel a booking or enquiry, set availability.
    - marketplace: approve a vendor, run a payout.
    - book_product: assign genres and topics, edit book metadata.
    - audiobooks: generate.
    - bookvault: send an order.
    - customers: create or edit a customer or address.
    - eco_impact: none.

    Each needs its tool, or a stated reason why an agent must not have it. staff_mfa reset and gdpr erasure should stay tool-less, deliberately.
13. **Apps with no in-app tests:** rbac (an authorization layer, protected), store_bootstrap, localization, linda_generated, and journal (a placeholder assert only).
14. **A DB write at boot.** `rbac/app.py:33` calls `Role.ensure_system_roles()` from `ready()` on every process start, management commands included. Move it to `post_migrate`.
15. **Manifests that claim missing features:**
    - journal: "Notion-style block editor", with no views.
    - brand_kit: "AI brand-kit generator", absent.
    - localization: "edit translations inline", read-only.
    - environments: "promotion", with no UI.
    - ai_content: still describes a removed auto-description hook.
    - ai_assistant `services/memory.py`, `forecasting.py`, `assembler.py`: 1-line stubs.
16. **Dead wiring:**
    - `demo_data/app.py:16` uses `requires_plugins`, which the registry doesn't read, yet the app imports book_product.
    - `dynamics/services.py:700` imports a non-existent `catalog.ProductReview`, so ratings are always `{}`. This is another cluster's app, found on the way.
17. **Store content shipped as platform code:** about 9.7k LOC in `booking_marketplace/management/commands/` (Montenegro), `cms/management/commands/seed_publisher_pages.py` and `seed_journal_articles.py` (dotbooks), and `demo_data/seeds.py` (1088 LOC bookstore). This inflates the LOC numbers and couples the shared apps to particular stores.
18. **Bookings have no money path.** `Booking`/`StayBooking` (`booking_marketplace/models.py:175,561`) have no FK to `orders.Order` or payments. If paid bookings are planned, they need a payment leg through orders, not a parallel table.
