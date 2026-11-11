<div align="center">

# Morpheus OS

### Launch a store you own. Let an AI run the back office. Keep every sale.

*Morpheus is a complete commerce platform you install on your own server: catalog, checkout, payments, shipping, tax, email, SEO, ad channels and an AI operator called Linda, in one codebase that already runs five live stores. No share of your revenue, no app tax, no lock-in.*

[![Status: beta](https://img.shields.io/badge/status-beta-f59e0b.svg)](docs/RELEASE_NOTES.md)
[![License: BUSL-1.1](https://img.shields.io/badge/License-BUSL--1.1-blue.svg)](#license)
[![Live stores](https://img.shields.io/badge/live-5%20stores%2C%20one%20codebase-ff5722.svg)](#five-live-stores-one-codebase)
[![Apps](https://img.shields.io/badge/apps-98%20built%20in-2563eb.svg)](#every-app-in-the-box)
[![Revenue share](https://img.shields.io/badge/revenue%20share-0%25-16a34a.svg)](#what-it-costs)

**[Install it](#install-it) · [See a live store](https://dotbooks.store) · [Have it set up for you](#have-it-set-up-for-you) · [How it compares](#how-it-compares) · [Questions](#questions-founders-ask)**

</div>

---

## Why founders pick Morpheus

**You keep your margin.** No percentage of your sales and no per-seat pricing: one licence per store. The things other platforms bill monthly, one app at a time (reviews, loyalty points, subscriptions, gift cards, affiliates, abandoned-cart email, B2B quotes, feeds for nine ad channels), are already here as 98 apps you switch on and off.

**You get an operator, not a chatbot.** Linda reads your catalog, orders and customers and does the work: refunds, stock, product copy, newsletters, reports, a brief every morning. Of the 220 tools Linda can use, the 69 that move money or delete things wait for your "yes", in your own words. A kill switch and a daily spend cap cover every AI call the store makes.

**Shoppers find you where they now start.** Search engines and AI assistants get what they need to read your store and send buyers to it: structured data built from your real prices, stock, shipping and returns, sitemaps, `llms.txt`, a ChatGPT Shopping feed, MCP servers, an Agentic Commerce Protocol checkout and a UCP manifest. The sale happens on your storefront, and the customer stays yours.

**You own all of it.** Your server, your Postgres database, your code. Every version becomes Apache 2.0 four years after it ships.

**You are EU-ready on day one.** The lowest price of the last 30 days on every sale (Omnibus), manufacturer and safety details on every product (GPSR), a mark on text an AI wrote (AI Act, Article 50), a cookie banner that every tag and every server-side send obeys, WCAG audits on every deploy, and checkout pages that run only the scripts they list (PCI DSS 4.0).

---

## Five live stores, one codebase

Every merge to `main` deploys to all five. Each has its own database, theme and set of apps; nothing is forked.

| Store | What it sells | What it proves |
|---|---|---|
| **[dotbooks.store](https://dotbooks.store)** | An independent bookshop: print, digital and audio | A deep vertical: print-on-demand through Bookvault, audiobooks, digital downloads with a buyer's library, filters by genre, topic, author, format and length |
| **[supernatural-shop.com](https://supernatural-shop.com)** | A longevity pantry: supplements and pantry foods, with guides that cite their sources | A general catalog with editorial content and dropshipping suppliers |
| **[montenegro-experience.me](https://montenegro-experience.me)** | Tours, stays and hidden gems from local hosts | A travel marketplace: bookable experiences, hotels, events, an enquiry inbox, English and Serbian |
| **[croatia-experience.me](https://croatia-experience.me)** | Experiences, hotels, places and events across Croatia | The same marketplace for a second country, in English and Croatian, with hotel stars from the Ministry of Tourism register |
| **[beta.irvingsurvival.com](https://beta.irvingsurvival.com)** | Survival and preparedness gear and guides, worldwide | A third catalog store with its own theme, a supply calculator and a readiness check; hidden from shoppers until launch |

A sixth store starts the way these did: install it, then describe the shop in one sentence.

---

## A normal day with Linda

```
› mark order #1042 refunded
  ⚠ refund $84.00 to Ada Whitfield — this needs your confirmation
› yes
  ✓ refunded · gift-card balance re-credited · customer emailed · audit row written

› which hardcovers are nearly out of stock?
  4 titles under 3 units — The Huguenots (1), Dune (2), …

› draft the October newsletter from last month's best sellers
  ✎ staged as a proposal — review it before it goes out
```

The refund waited because it moves money. The approval is recorded against that exact refund and only your own next message can spend it, so a product description or a customer note that tries to talk Linda into a refund gets a refusal and an audit row. Staff see only the tools their role allows, and an outside agent's "yes" never counts as yours.

Linda works in the dashboard chat, in a command bar on every page, on a schedule you set (automations), and for outside agents over MCP and GraphQL. Pick the model per message from twelve providers (OpenAI, Anthropic, Gemini, DeepSeek, Qwen Cloud, a local Ollama and more), with your own API key.

---

## Install it

### 1. Try it on your laptop (about 15 minutes)

You need **Python 3.12** and **Redis** (`brew install redis && brew services start redis` on a Mac, `sudo apt install redis-server` on Ubuntu).

```bash
git clone https://github.com/magnetoid/Morpheus.git
cd Morpheus
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.lock.txt
printf 'DEBUG=True\nDATABASE_URL=sqlite:///db.sqlite3\nMORPHEUS_EXTRA_APPS=plugins.installed.demo_data\n' > .env
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

The first `migrate` builds every app's tables and takes a few minutes. Then open **http://127.0.0.1:8000/dashboard/** and sign in with the email and password you just chose. Fill the store one of two ways:

- **See a full store right away:** `python manage.py morph_seed_demo` loads a sample bookshop with 50 books, genres, collections and customers in under a minute.
- **Start your own:** add an AI key under **Settings → AI**, open **/dashboard/apps/store_bootstrap/start/** and describe your shop in one sentence. You get a brand voice, categories and ten to twelve starter products to edit.

The shop itself is at **http://127.0.0.1:8000/**.

### 2. Go live on your own server

The five live stores run on [Coolify](https://coolify.io) on one server. On a VPS with 2 GB of RAM (4 GB recommended): add the repository as a Docker Compose resource, paste the environment variables, point your domain at the `web` service and deploy. `docker-compose.yml` brings up the web app, a worker, the scheduler, Postgres and Redis. Step by step: [`docs/deploy-coolify.md`](docs/deploy-coolify.md).

Each later update backs the database up before it migrates, and a release whose migrations the previous version could not run on is refused before it ships.

### 3. Take real orders

Installing, evaluating and building on Morpheus is free. Before you sell, write for your per-store licence: [marko@morpheus.direct](mailto:marko@morpheus.direct). [What it costs](#what-it-costs) explains the terms.

### Have it set up for you

Rather not run it yourself? Your store can be set up, themed, moved over from Shopify or WooCommerce and run with Linda for you. Write to **[marko@morpheus.direct](mailto:marko@morpheus.direct)** with what you sell, where you sell it today and what you want to change.

---

## How it compares

| | Morpheus | Shopify | WooCommerce | Medusa · Saleor |
|---|---|---|---|---|
| **What the platform takes** | A licence per store; no share of sales, no seats | A monthly plan, a fee per sale unless you use Shopify Payments, and paid apps | Free plugin; hosting and paid extensions | Free and open source; you build what is missing |
| **Who owns the store** | You: your server, database and code | Shopify | You | You |
| **AI that does the back-office work** | Built in, with approvals, spend caps and an audit trail | Sidekick, inside Shopify | Plugins | Bring your own (read-only MCP) |
| **Ready for AI shoppers** | MCP servers, ACP checkout (off until you switch it on), UCP manifest, verified agents | Ahead: UCP on by default, catalog, cart and checkout for agents | Plugins | ACP apps and tutorials |
| **Built in, not bought** | 98 apps: loyalty, reviews, subscriptions, affiliates, marketplace, B2B quotes, nine ad channels, four dropshipping suppliers | Many through apps, often paid | Many through extensions, often paid | Modules and recipes you assemble |
| **EU rules (Omnibus, GPSR, AI Act, consent)** | Built in | Partly, plus apps | Plugins | Not built in |
| **Order editing, partial shipments, labels, delayed card capture** | **Not yet**, in the plan below | Yes | Mostly, some through plugins | Mostly |

Morpheus is ahead on owning the store, the AI operator and EU compliance, and behind on the second layer of the order engine. That gap is written down with evidence in [`docs/plans/platform-gap-analysis-2026-11.md`](docs/plans/platform-gap-analysis-2026-11.md), with the release that closes each part. Tax shipped in v0.149.0, promotions in v0.150.0 and stock operations in v0.152.0.

---

## What it costs

- **Free** to install, read, evaluate, develop on and test, under the [Business Source License 1.1](LICENSE).
- **A licence per store** once it takes real orders. No revenue share, no seat count, no app fees for the 98 apps.
- **Your own running costs:** a server (the five live stores share one), your AI provider's usage under a daily cap you set, and your payment provider's fees.
- **No dead end.** Each version becomes Apache 2.0 four years after it is published. Versions up to v0.76.0 are already Apache 2.0.

---

## Questions founders ask

**Do I need a developer?**
Not to try it: the commands above are the whole install. Running it in production means running a server; Coolify turns that into a few screens, or [have it set up for you](#have-it-set-up-for-you).

**Can I move from Shopify or WooCommerce?**
Yes. Importers bring products across from Shopify and WooCommerce, and a CSV import covers anything else. Running one twice does not duplicate anything.

**What stops the AI doing something stupid?**
Every tool declares what it may touch, and a caller sees only what it may call. Anything that moves money or deletes data waits for your own reply, bound to that exact change and usable once. A kill switch, daily run and spend caps and per-action price and refund limits are yours to set, and every call and every refusal is logged.

**Which payments work?**
Stripe (cards, Apple Pay, Google Pay, Link, Klarna), PayPal, cash on delivery and bank transfer. A method is offered only once its credentials are in. The live stores currently sell with cash on delivery; the Stripe card flow has not yet been run against a live Stripe account.

**Is it stable enough to run a business on?**
It is a 0.x beta that five stores run on daily. There have been 349 releases in 144 days, and 5,962 tests run before each one. Every deploy backs up the database before migrating. When a release leaves a store down, the store goes back to the release before it on its own.

**What happens if you disappear?**
The code is public and yours to run, your data sits in your own Postgres, and every version turns Apache 2.0 four years after release.

**Is it open source?**
It is source-available: free to read and build on, with a licence needed for production. That licence pays for the work.

---

## What isn't finished yet

You would find these on day two, so here they are now:

- **Orders after checkout:** no order editing yet, a shipment always covers the whole order, there are no shipping labels, and cards are charged at checkout rather than when the order ships.
- **Pricing depth:** B2B price lists and net terms exist, but they do not change what a customer is charged yet.
- **Returns** are handled by staff; a customer cannot start one yet.
- **About eighteen apps do less than their names suggest**, and each one says so in its own help: 3D and AR previews, the feed-style product rails, post-purchase emails, the storefront stylist chat, drops, the discovery quiz.
- **Roles and permissions** guard 291 staff pages but only record what they would deny until a store switches them to enforce.
- **Updates from morpheus.direct:** a store that does not run from a git checkout is not told when a new release is out. A signed update channel on morpheus.direct is being designed ([`docs/plans/morpheus-direct-distribution-2026-11.md`](docs/plans/morpheus-direct-distribution-2026-11.md)).

The order these get done in is in [`docs/plans/platform-gap-analysis-2026-11.md`](docs/plans/platform-gap-analysis-2026-11.md), and each release is in [`docs/RELEASE_NOTES.md`](docs/RELEASE_NOTES.md).

---

## For your technical co-founder

### How it is built

The kernel in `core/` is a small set of extension points: auth, an event bus, settings, the request lifecycle, i18n, observability, the agent runtime, the AI safety boundary (`core/safety.py`) and a self-improvement loop. Everything else is an app under `plugins/installed/<name>/` that reaches the rest only by contributing a storefront block, a dashboard page, a settings panel or a hook subscriber.

Two rules hold for every app, and CI tests both:

- **Delete its folder** and the feature is gone, with no dangling route, template or import anywhere.
- **Switch it off** in the dashboard and every surface it added disappears with it.

`core/` imports no app at all; a ratchet in CI keeps that number at zero, and a second one stops apps importing each other except through declared dependencies. The storefront reads GraphQL, never the ORM, so a headless front end gets the same data ([`docs/HEADLESS.md`](docs/HEADLESS.md)). Apps are written against three SDK doors: `morpheus.app`, `morpheus.core` and `morpheus.theme`.

**Stack:** Django 6.1 on Python 3.12, PostgreSQL 16, Redis, Celery with beat, Strawberry GraphQL and DRF, djmoney, allauth, a Tailwind dashboard, and Janus as the agent engine. Container-first: `Dockerfile`, `docker-compose.yml` and Kubernetes manifests.

### By the numbers

Measured at **v0.152.1 (11 November 2026)** by `scripts/measure_readme.py`, which boots the app with every opt-in app on and reads the registries. Re-run the script rather than editing a figure by hand; each row names its source of truth, and that source wins.

| Metric | Value | Source of truth |
|---|---|---|
| Apps in the tree | **98** (92 on by default + 6 opt-in: the travel booking vertical, four dropshipping apps and demo data) | `plugins/installed/` · `MORPHEUS_DEFAULT_APPS` in `morph/settings.py` |
| Typed events on the hooks bus | **120**, with **335** subscriptions | `MorpheusEvents` in `core/hooks.py` |
| Agent tools | **220**, 69 of them need a human's approval | `core/agents/registry.py` at boot |
| MCP token scopes | **40** | `plugins/installed/agent_mcp/scopes.py` |
| RBAC capabilities | **32**, gating **291** views | `plugins/installed/rbac/models.py` · `@require_capability` |
| GraphQL surface | **36** queries · **50** mutations · **101** types | `api/schema.py` |
| URL routes | **685**, of which **306** dashboard | a walk of the URL resolver |
| Dashboard pages · settings panels · storefront blocks | **124** · **57** · **78** across 20 theme slots | the app registry at boot |
| Scheduled jobs · management commands | **61** · **66** | `CELERY_BEAT_SCHEDULE` · `manage.py help` |
| Payment gateways | **5**: Stripe, PayPal, cash on delivery, bank transfer, a staff-only test gateway | `payments.gateway_registry` |
| Production releases since v0.1.0 (2026-06-20) | **349 in 144 days** | `docs/RELEASE_NOTES.md` |
| Tests | **5,962** test functions | `def test_` in the tree |
| Python | **~345k lines** in `core/`, `plugins/`, `themes/`, `api/`, `morph/`, `morpheus/`, `scripts/` (~96k of it tests) | the tree |
| Templates, CSS and JS | **837** templates · **~88k** lines | the tree |
| Migrations | **283** | `*/migrations/` |
| Architecture decision records | **39** | `.torsor/architecture/decisions/` |
| `core/` imports from apps | **0, enforced** | `scripts/check_core_boundary.py` |
| Live stores on one codebase | **5** | [above](#five-live-stores-one-codebase) |

### Every app in the box

Each app below is described from its own manifest. The always-current list is **Settings → Apps** in the dashboard, and each app's guide is under **Help**.

<details>
<summary><strong>Commerce core</strong> — 8 apps</summary>

| App | What it does |
|---|---|
| `catalog` | Products, variants, categories, collections and attributes; every displayed and charged price flows through one price seam |
| `orders` | Cart, the order lifecycle, fulfilment, refunds through one locking service, transactional email, invoices, notes and CSV export |
| `customers` | Accounts, addresses, passwordless and password sign-in, the self-service account hub |
| `inventory` | Warehouses, stock levels and movements, low-stock alerts, atomic reservations, a stockout forecast |
| `payments` | The payment engine: Stripe (Payment Element, webhooks, refunds), PayPal, bank transfer, cash on delivery and a staff-only test payment; a gateway without credentials is never offered; a fraud score on every order (velocity, address mismatch, refund history) |
| `shipping` | Zones and rates: flat, by weight, by order total, free over a threshold (the dashboard enters flat rates so far); live Shippo and EasyPost quotes |
| `tax` | Regions and rates from the shipping address: reduced rates per product category, every rate a region holds (compound ones on top), tax on the price after discounts and, when switched on, on shipping; prices that include tax |
| `draft_orders` | Staff-built draft orders and quotes, shared with the customer, converted to a real order on payment |

</details>

<details>
<summary><strong>Pricing, promotions & tenders</strong> — 7 apps</summary>

| App | What it does |
|---|---|
| `promotions` | A rule engine: stack predicates (cart total, channel, country, customer group, product) with % off, fixed off, free shipping or a gift; time-bounded, audit-logged |
| `marketing` | Coupons, the discount engine, email campaigns, abandoned-cart recovery |
| `gift_cards` | Issue, redeem and audit gift cards on an append-only ledger; re-credited pro rata on refund |
| `loyalty_points` | Points on paid orders, shown on the account page, redeemed at checkout at a configurable rate |
| `subscriptions` | Recurring billing and delivery: plans, replenishment and curated-box kinds, pause / skip / swap with an audit log, invoices; manual provider out of the box, Stripe Billing adapter |
| `markets` | Per-country pricing, currency and locale, resolved from the visitor's country |
| `b2b` | Quotes with a full lifecycle, per-account price lists and net-terms agreements for business buyers |

</details>

<details>
<summary><strong>Merchandising & personalisation</strong> — 7 apps</summary>

| App | What it does |
|---|---|
| `dynamics` | Personalised merchandising blocks (for-you, related, recently viewed, bought-together) configured per theme slot — carousels render as the theme's own rows — with an autopilot that proposes layouts |
| `rails` | Meant for five feed-style rails (For You, Restocked, Recently Viewed, Trending With Your Cohort, Looks Like You); none of them shows anything yet |
| `personalisation` | Co-purchase recommendations and propensity-ordered product lists, all consent-gated |
| `discovery_quiz` | A zero-party-data quiz that ends in a personalised category view and feeds segmentation with consent |
| `lookbook` | Editorial product bundles with their own pages, added to cart as one line or as individual products; AI auto-looks from the co-purchase graph |
| `drops` | Scheduled drops, raffle-by-waitlist for limited stock, push notifications, a stock-equalising queue, post-sellout waitlists |
| `metafields` | Schema-less custom fields on any record — products, customers, orders, pages |

</details>

<details>
<summary><strong>Storefront & content</strong> — 16 apps</summary>

| App | What it does |
|---|---|
| `storefront` | The theme-powered storefront; it consumes the GraphQL API internally and never touches the ORM |
| `cms` | Pages, reusable blocks, named menus and merchant-defined forms, all theme-overridable |
| `richtext` | A self-hosted Lexical rich-text editor used by the product and page forms; no CDN, no build step at deploy |
| `media` | A unified asset manager for images, video, audio, PDFs, spreadsheets, documents and digital downloads |
| `product_gallery` | Cover plus square slider on product pages, native scroll-snap, no JS dependency |
| `product_stories` | Scroll-snap "why you'll love it" story blocks, ordered per product, edited in the dashboard |
| `product_videos` | YouTube, Vimeo or raw embeds on the product page |
| `media_3d` | Meant for per-product 3D and AR previews and shoppable video; neither works yet |
| `bookstore_3d` | A first-person 3D walkthrough with real catalog products on the shelves (three.js, no build step) |
| `immersive_pdp` | A sticky, theme-styled add-to-cart bar with an edition picker and quantity |
| `flipbook` | A 3D page-flipping preview for any product with a PDF attached |
| `webstories` | Google-indexable AMP Web Stories generated from product images, embedded on the product page; indexing can be switched off |
| `live_commerce` | Scheduled live shopping events: embedded stream, pinned buyable products, UTM-attributed conversion, replay |
| `pwa` | An installable, offline-capable storefront: manifest, service worker, icons |
| `motion` | Page transitions, scroll-snap story progress, button micro-feel and skeleton states, tinted to the brand |
| `advanced_ecommerce` | Recently-viewed, free-shipping progress and low-stock badges on the storefront; bulk price edit and low-stock alerts in the dashboard |

</details>

<details>
<summary><strong>CRM, retention & growth</strong> — 8 apps</summary>

| App | What it does |
|---|---|
| `crm` | Leads, accounts, deals and pipelines, an interactions timeline, follow-up tasks, customer notes, a support inbox and chat, and an account-manager agent |
| `reviews` | Customer reviews on the product page with merchant moderation, and the star rating, verified-buyer share and recent purchases under the price |
| `wishlist` | Saved items for customers and guests, shareable links, agent tools for the concierge |
| `cart_abandonment` | Detects stale carts and runs the consent-checked, multi-step recovery email drip |
| `post_purchase` | One suggested product on the order confirmation page; schedules the chain per order — shipment tracking → delivered → review request → NPS survey; the sending itself is not wired up yet |
| `newsletter` | Signup popups and a double-opt-in subscriber list; sends reuse the campaign engine |
| `affiliates` | Affiliate links, attribution, conversions, commission tiers, payouts, embeddable shop widgets and an affiliate portal |
| `returns_portal` | Exchange or store credit as first-class return resolutions, with feedback routed to the CRM |

</details>

<details>
<summary><strong>Sales channels & marketplaces</strong> — 11 apps</summary>

| App | What it does |
|---|---|
| `channels` | One operator view of every channel: connection status, feed coverage, pixel state and ROAS |
| `google_shopping` | The Merchant Center feed with a coverage dashboard, plus Google Ads conversions and reporting |
| `meta_commerce` | Facebook and Instagram catalog feed and API push, the Meta Pixel and Conversions API, campaign reporting |
| `tiktok_commerce` | TikTok catalog feed, Pixel and Events API, campaign reporting and management |
| `pinterest_commerce` | Pinterest catalog feed, the Tag and Conversions API, the Ads API |
| `microsoft_commerce` | Microsoft Merchant Center feed and the UET conversion tag |
| `snapchat_commerce` | Snapchat catalog feed, the Snap Pixel and Conversions API, campaign reporting |
| `openai_shopping` | ChatGPT Shopping feed in OpenAI's feed specification (JSONL, served and pushed), with the seller, country, eligibility and return fields — Perplexity takes the same file |
| `reddit_ads` | The Reddit Pixel, Conversions API and Ads API |
| `amazon_ads` | Sponsored Products campaign management and performance reporting over the Amazon Ads API |
| `marketplace` | Multivendor: vendor onboarding and applications, a vendor portal, vendor editing in the dashboard (an old address redirects), vendor orders, payouts, reports |

</details>

<details>
<summary><strong>AI & agents</strong> — 9 apps</summary>

| App | What it does |
|---|---|
| `agent_core` | Linda's tool catalogue — catalog reads and writes, order ops, inventory, content, analytics — and the kernel runtime shared by sub-agents |
| `agent_mcp` | The agent gateway: four MCP servers, the UCP discovery manifest, trusted-agent and Web Bot Auth verification, API tokens with scopes, and Janus for external agents |
| `agentic_checkout` | Agentic Commerce Protocol checkout sessions and a product feed for AI buyers such as ChatGPT Instant Checkout (opt-in) |
| `ai_assistant` | Product embeddings, semantic search, recommendations, dynamic pricing and configuration for twelve AI providers (OpenAI, Anthropic, Gemini, DeepSeek, Qwen Cloud, Ollama and more) |
| `ai_content` | The store-wide brand voice every AI generation reads, product-description generation, the content and assets studio |
| `ai_stylist` | A conversational shopping assistant with a shopper-facing persona and its own audit trail; set up, but not yet shown on the storefront |
| `janus` | The engine behind Linda: on/off, model, step and time caps, standing instructions, bundled skills, and what she has learned |
| `morpheus_brain` | One console for code quality, errors and SEO health, with an AI advisory briefing on the whole site |
| `store_bootstrap` | Type one sentence; get a brand voice, a category tree and a starter catalogue |

</details>

<details>
<summary><strong>Search, SEO, analytics & localisation</strong> — 4 apps</summary>

| App | What it does |
|---|---|
| `seo` | The owned head document, the JSON-LD graph, sitemaps, robots with a 2026 AI-crawler matrix, redirects, index rules, title templates, an audit and eleven dashboard pages |
| `analytics` | Full-funnel analytics: pageviews, sessions, search, cart, checkout, orders and agent activity; real-time, funnels, cohorts, attribution; queryable by Linda |
| `tracking` | Google Analytics 4 and Tag Manager, server-side via the Measurement Protocol and client-side via the dataLayer, Consent Mode v2 |
| `localization` | Inline translation editing, target languages and hreflang alternates over the core i18n kernel |

</details>

<details>
<summary><strong>Operations, security & compliance</strong> — 18 apps</summary>

| App | What it does |
|---|---|
| `admin_dashboard` | The merchant dashboard (Tailwind CSS + shadcn/ui), host to every contributed page and settings panel |
| `rbac` | Roles and permissions: six role templates, 32 capabilities, bindings optionally scoped per channel, `log` → `enforce` per store |
| `staff_mfa` | A TOTP second factor for staff: authenticator enrolment, recovery codes, required-for-staff mode, an audited break-glass reset |
| `staff_sso` | OIDC / SAML 2.0 staff sign-in (Okta, Entra, Google Workspace) with JIT provisioning and domain or group gating |
| `gdpr` | Article 15 export and Article 17 erasure as self-service, an auditable request trail, seeded Privacy / Terms / Imprint pages |
| `consent` | A cookie banner with per-category opt-in and an auditable log of every decision, which every tag and every server-side send obeys |
| `observability` | The audit-log surface and the error log |
| `backups` | Nightly database and media backups with retention, scheduled through beat |
| `demo_data` | Seed data for a demo bookstore and an on-demand product generator themed by the active storefront theme (opt-in) |
| `webhooks_ui` | Webhook endpoints, HMAC-SHA256-signed deliveries, a delivery log with retry and replay |
| `notifications_center` | A persistent staff inbox for what needs follow-up: pending RMAs, low stock, failed agent runs, overdue tasks |
| `workflows` | No-code automation: a trigger, a condition, one or more actions — including "run an agent skill" |
| `cloudflare` | Cache purge on product and collection changes, DNS integration |
| `importers` | Idempotent migration from Shopify and WooCommerce, plus bulk CSV import and export |
| `product_safety` | Shows each product's manufacturer, EU responsible person and safety warnings on its page, as EU product safety rules require |
| `feature_adoption` | Per-install feature-usage aggregates and an install-health score, with no PII |
| `feedback` | Staff bug reports with a screen capture and the recent JavaScript errors attached, as tickets under Settings |
| `release_notes` | Help for every app inside the dashboard (a guide per app next to what the running code offers), About Morpheus OS, and Version & updates |

</details>

<details>
<summary><strong>Verticals</strong> — 10 apps</summary>

| App | What it does |
|---|---|
| `book_product` | Books as a first-class product type: author, format and paper, page count, a cover-PDF 3D preview, genres, series and taxonomies, and shop filters by genre, topic, author, format and length |
| `audiobooks` | A priced audiobook edition with a modal player on the product page; ElevenLabs narration |
| `bookvault` | Print-on-demand fulfilment through Bookvault: live shipping quotes at checkout, paid orders sent automatically, a bulk product linker |
| `eco_impact` | A book's paper, wood and CO₂ footprint on its page, and plant-a-tree at checkout, tracked as a fund |
| `digital_products` | Token-protected downloads with expiry and count limits, emailed automatically after payment |
| `booking_marketplace` | Bookable experiences and stays from local hosts — each listing a catalog product — destination guides, hotels and an events calendar, a search that reads accents, Cyrillic and typos, and an operator inbox (opt-in; runs the Montenegro store) |
| `dsers` | Dropshipping through DSers (AliExpress): link each variant to its supplier item, export paid orders as DSers' CSV, import the tracking numbers and ship the orders (opt-in; runs on supernatural-shop) |
| `zendrop` | Dropshipping through Zendrop: connect over its MCP server and see what the account can do, map variants to Zendrop products, work paid orders from a copy-ready order sheet, ship them with Zendrop's tracking (opt-in; runs on supernatural-shop) |
| `cjdropshipping` | Dropshipping through CJdropshipping's Open API: search CJ's catalogue and import products as priced drafts, send paid orders to CJ automatically and pay them from the CJ balance, ship them with the tracking CJ's signed webhooks report (opt-in) |
| `aliexpress` | Dropshipping through AliExpress' official DS API: connect the AliExpress account by OAuth, import products as priced drafts, place paid orders automatically (one per seller) with their payment deadline, ship them once every seller's tracking is in (opt-in) |

</details>

### Run the tests

```bash
# Pin an in-memory database: a bare `manage.py test` looks for the Docker `db` host.
DATABASE_URL='sqlite:///:memory:' python manage.py test plugins.installed.<name>

# The whole suite, with the opt-in apps on so their tests run too
DATABASE_URL='sqlite:///:memory:' MORPHEUS_EXTRA_APPS='plugins.installed.booking_marketplace,plugins.installed.dsers,plugins.installed.zendrop,plugins.installed.cjdropshipping,plugins.installed.aliexpress' python manage.py test
```

CI also runs `ruff`, the two boundary ratchets, `manage.py check`, `makemigrations --check`, every migration against real Postgres, `release --check`, `bandit` and `pip-audit`. After each deploy it waits for every store to report the new version, then runs axe on each store's live pages and Lighthouse on dotbooks.

### Documentation

| Topic | Doc |
|---|---|
| Architecture and the request lifecycle | [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) · [`ARCHITECTURE.md`](ARCHITECTURE.md) |
| Building an app · a theme | [`docs/PLUGIN_DEVELOPMENT.md`](docs/PLUGIN_DEVELOPMENT.md) · [`docs/THEME_DEVELOPMENT.md`](docs/THEME_DEVELOPMENT.md) |
| GraphQL and REST · what is stable | [`docs/MORPHEUS_API.md`](docs/MORPHEUS_API.md) · [`docs/API_STABILITY.md`](docs/API_STABILITY.md) |
| Agents: MCP, ACP, UCP | [`docs/MCP_SERVER.md`](docs/MCP_SERVER.md) · [`docs/AGENT_PROTOCOLS.md`](docs/AGENT_PROTOCOLS.md) |
| Going live: payments, email, keys | [`docs/REVENUE_PATH.md`](docs/REVENUE_PATH.md) · [`docs/deploy-coolify.md`](docs/deploy-coolify.md) |
| Updating · operations and recovery | [`docs/UPDATING.md`](docs/UPDATING.md) · [`docs/OPERATIONS_RUNBOOK.md`](docs/OPERATIONS_RUNBOOK.md) |
| Compliance and security | [`docs/COMPLIANCE.md`](docs/COMPLIANCE.md) · [`SECURITY.md`](SECURITY.md) |
| Gap analysis and the plan | [`docs/plans/platform-gap-analysis-2026-11.md`](docs/plans/platform-gap-analysis-2026-11.md) |
| House rules for AI-assisted work | [`CLAUDE.md`](CLAUDE.md) · [`AGENTS.md`](AGENTS.md) |
| Every release | [`docs/RELEASE_NOTES.md`](docs/RELEASE_NOTES.md) · breaking changes in [`docs/MIGRATING.md`](docs/MIGRATING.md) |

---

## Get in touch

Morpheus is built and run by **Marko Tiosavljevic**, who answers every message personally.

**[marko@morpheus.direct](mailto:marko@morpheus.direct)** · [morpheus.direct](https://morpheus.direct)

Write if you want a store on Morpheus, want your production licence, want to build an app or theme on it, or want a walkthrough of a live store. Say what you sell, where you sell it today and what you want to change, and you will get a straight answer.

## Contributing

Read [`CONTRIBUTING.md`](CONTRIBUTING.md) and the house rules in [`CLAUDE.md`](CLAUDE.md). In short: it is an app unless it is genuinely foundational, it ships with its migration, its tests and its help, it disappears cleanly when switched off, and anything that deploys bumps the version.

## License

**[Business Source License 1.1](LICENSE)**, in plain words:

- Read the code, run it to evaluate, develop and test, change it and pass it on under the same terms, for free.
- **Running a store on it, or any other business use, needs a commercial licence**: one per store, with no revenue share and no seat count. Write to [marko@morpheus.direct](mailto:marko@morpheus.direct).
- Four years after a version is published it becomes Apache 2.0 automatically. Versions up to v0.76.0 were published under Apache 2.0 and stay that way.

The licence is source-available rather than open source, by design: it keeps the code readable and your store yours while paying for the work. Third-party components keep their own licences.

<div align="center">

**[dotbooks.store](https://dotbooks.store) · [supernatural-shop.com](https://supernatural-shop.com) · [montenegro-experience.me](https://montenegro-experience.me) · [croatia-experience.me](https://croatia-experience.me) · [beta.irvingsurvival.com](https://beta.irvingsurvival.com)**

*Morpheus OS: a store you own, run by an AI you can trust, found by people and by agents.*

**[Install it](#install-it) · [marko@morpheus.direct](mailto:marko@morpheus.direct)**

</div>
