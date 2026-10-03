<div align="center">

# Morpheus OS

### Commerce you own. Run by an AI you can actually trust with the keys. Bought by agents.

*Describe your shop in one sentence and get a real, stocked storefront. Toggle 109 capabilities on and off like apps. Then hand the back office to an AI operator who knows your catalog, briefs you every morning, and proposes improvements to her own source code — every one of them reviewed by a panel of independent models, and then by you.*

[![License: BUSL-1.1](https://img.shields.io/badge/License-BUSL--1.1-blue.svg)](LICENSE)
[![Live stores](https://img.shields.io/badge/live-3%20stores%2C%20one%20codebase-ff5722.svg)](#-three-live-stores-one-codebase)
[![Apps](https://img.shields.io/badge/apps-109%20toggleable-2563eb.svg)](#-whats-in-the-box-all-109-apps)
[![AI operator](https://img.shields.io/badge/AI-built--in%20operator%20(Linda)-e11d48.svg)](#-meet-linda--the-ai-operator)
[![Agentic](https://img.shields.io/badge/agentic-MCP%20%2F%20ACP%20%2F%20UCP-7c3aed.svg)](#-agentic-commerce-be-transactable-by-ai)
[![Stack](https://img.shields.io/badge/django%206-postgres%20%C2%B7%20celery%20%C2%B7%20graphql-092e20.svg)](#-tech-stack)
[![Contact](https://img.shields.io/badge/contact-marko%40morpheus.direct-0ea5e9.svg)](mailto:marko@morpheus.direct)

**[▶ See it live](https://dotbooks.store) · [✉ Talk to us](#-get-in-touch) · [🚀 Run your own](#-quick-start) · [🧩 What's in the box](#-whats-in-the-box-all-109-apps) · [🧱 Architecture](#-architecture-a-small-kernel-a-deep-ecosystem) · [🧭 Roadmap](#-roadmap) · [📚 Docs](#-documentation)**

</div>

---

> **Want a store on Morpheus, want to build on it, or want to talk about where commerce is going?**
> Write to **[marko@morpheus.direct](mailto:marko@morpheus.direct)** — Marko Tiosavljevic builds and runs the platform, and answers every message himself. More at [morpheus.direct](https://morpheus.direct). Details in [Get in touch](#-get-in-touch).

---

## The problem with every other option

**Hosted SaaS rents you your own store.** You pay a percentage of every sale, then pay again for the apps that make it work, and the AI features arrive as a per-seat upsell that runs on somebody else's infrastructure, trained on somebody else's roadmap. The day the pricing changes, you have no move.

**Open-source alternatives hand you a codebase and wish you luck.** You own the code, which means you own the integration work, the agent surface nobody has built yet, and the governance layer that would make an LLM safe to point at your refund button.

**And both are about to have the same problem.** A growing share of shopping now starts inside an assistant. If a model can't read your catalog, quote your real shipping, and complete a cart, you don't lose a ranking — you lose the conversation entirely, to whoever the model *can* transact with.

Morpheus is the third option: **a full commerce engine you run yourself, built from the ground up to be operated by an AI and transacted with by one.** It already runs three live stores — a bookshop, a natural-goods shop and a travel marketplace — from one codebase.

---

## What makes it different

Three convictions, and each one shows up as code rather than a roadmap item.

### 1. The AI is staff, not a subscription

One generalist operator — **Linda** — runs on your servers. She reads your catalog, executes real back-office work through a typed tool registry of 184 tools, writes you a morning brief, and opens pull requests against her own platform.

That last sentence is only safe because of the part nobody advertises: **the harness.** Every tool call passes a scope check, a budget, a deadline, and an approval gate. Destructive writes create a server-side, fingerprint-bound, single-use approval record and **fail closed** if the approver is unreachable. An agent can stage a change as a proposal instead of executing it. Merchants get a kill switch and daily spend caps. Every call and every refusal writes an audit row.

> **The harness is the product.** Anyone can bolt an LLM onto a store. The hard part — the part that takes a year and a lot of scars — is the safety layer that makes giving an agent real authority a reasonable thing to do.

### 2. Everything is an app, and disabling one leaves no trace

The kernel is a small set of extension points. Every shipped capability — catalog, checkout, loyalty, 3D storefronts, ad channels, B2B — lives in its own folder and reaches the rest of the system only by *contributing*: a storefront block, a dashboard page, a hook subscriber. Never by editing another layer's files.

Two tests every feature has to pass:

- **Delete** its folder → the feature is gone, with no dangling route, template, or import anywhere else.
- **Disable** it in the dashboard → *every* surface it added — nav entries, settings pages, storefront blocks, URLs — vanishes.

This isn't a style guide. It's enforced by CI ratchets that can only ever move in one direction, and by a test suite that toggles apps off and asserts their surfaces disappear.

### 3. You are legible to machines — and never intermediated by one

Morpheus ships a real MCP server, an Agentic Commerce Protocol checkout, a live-computed UCP manifest, `llms.txt` and `agents.md`, and a structured-data layer that describes your products the way Google's 2026 merchant rules actually specify.

The design goal is deliberate: shoppers **discover** you inside an assistant and **convert on your storefront**. You keep the customer relationship, the conversion surface, and Merchant-of-Record status.

---

## Table of contents

- [Why Morpheus](#-why-morpheus)
- [By the numbers](#-by-the-numbers)
- [Three live stores, one codebase](#-three-live-stores-one-codebase)
- [Meet Linda — the AI operator](#-meet-linda--the-ai-operator)
- [Agentic commerce: be transactable by AI](#-agentic-commerce-be-transactable-by-ai)
- [Found by search, and by answer engines](#-found-by-search-and-by-answer-engines)
- [A tour: shoppers, merchants, developers](#-a-tour-shoppers-merchants-developers)
- [Architecture: a small kernel, a deep ecosystem](#-architecture-a-small-kernel-a-deep-ecosystem)
- [What's in the box: all 109 apps](#-whats-in-the-box-all-109-apps)
- [It runs itself](#-it-runs-itself)
- [The self-improvement loop](#-the-self-improvement-loop)
- [Safety, security & compliance](#-safety-security--compliance)
- [Roadmap](#-roadmap)
- [What this is not (yet)](#-what-this-is-not-yet)
- [Tech stack](#-tech-stack)
- [Quick start](#-quick-start)
- [Project structure](#-project-structure)
- [Development workflow](#-development-workflow)
- [Project memory: torsor-helper](#-project-memory-torsor-helper)
- [Deployment](#-deployment)
- [Documentation](#-documentation)
- [Get in touch](#-get-in-touch)
- [Contributing](#-contributing)
- [License](#-license)

---

## ✨ Why Morpheus

| | Morpheus | Hosted SaaS (Shopify/BigCommerce) | Other open source (Woo/Medusa/Saleor) |
|---|---|---|---|
| **AI operator** | Built in, governed, on *your* infra | Add-on / per-seat copilot | Bring your own |
| **Agent-transactable** | MCP + ACP + UCP, native | Emerging, platform-mediated | Rare |
| **Feature model** | 109 apps, disable-safe by construction | Apps (billed, sandboxed) | Extensions / modules |
| **Sales channels** | 8 ad/commerce channels + a multivendor marketplace, built in | Per-channel apps | Per-channel extensions |
| **Migration in** | Shopify, WooCommerce, Magento, BigCommerce, CSV importers | — | Varies |
| **Own your data & code** | Yes — self-hosted; source-available under BUSL-1.1, each version turning Apache 2.0 after four years | No | Yes |
| **Platform fees** | A per-store licence; no revenue share, no seat count | % of revenue + app fees | None |
| **Self-improving** | Code changes reviewed by an LLM panel, then by you | — | — |
| **EU AI Act ready** | Art. 50 disclosure + evidence export | Varies | Bring your own |

**Who this is for**

- **Merchants** who want capability at the level of a hosted platform without paying a share of every order to get it — and who would rather have a store built and run for them than learn a platform. *([Talk to us](#-get-in-touch).)*
- **Agencies and developers** who want a real app model, three SDK doors, a documented GraphQL / REST / MCP surface and a test suite that already toggles every app off and on.
- **Teams** who want an AI staff member with real guardrails rather than a chat window bolted to an admin panel.
- **Builders, partners and investors** who can see where commerce is heading and would rather own the surface an agent talks to than rent it.

---

## 📊 By the numbers

Measured at **v0.76.0 (3 October 2026)** by a script over the tree, not from memory. Counts drift with every release — each row names its source of truth, and that source wins over this table. The dashboard's **Settings → About Morpheus** page is the always-current catalogue.

| Metric | Value | Source of truth |
|---|---|---|
| Toggleable apps in the tree | **109** (108 on by default + 1 opt-in vertical) | `plugins/installed/` · `MORPHEUS_DEFAULT_APPS` in `morph/settings.py` |
| Typed events on the hooks bus | **94**, with **256** subscriptions | `MorpheusEvents` in `core/hooks.py` |
| Agent tools in the typed registry | **184** — 47 of them require a human's approval | `core/agents/registry.py` at boot |
| MCP token scopes | **38** | `plugins/installed/agent_mcp/scopes.py` |
| RBAC capabilities | **32** · gating **249 views** | `plugins/installed/rbac/models.py` · `@require_capability` sites |
| GraphQL surface | **41** queries · **50** mutations · **114** types | `api/schema.py` |
| URL routes | **626**, of which **261** dashboard | `python manage.py show_urls`-style walk of the resolver |
| Dashboard pages · settings panels · storefront blocks | **109** · **66** · **80** across 19 theme slots | the app registry at boot |
| Scheduled jobs · management commands | **57** · **58** | `CELERY_BEAT_SCHEDULE` · `manage.py help` |
| Payment gateways | **5** — Stripe, PayPal, cash on delivery, bank transfer, sandbox | `payments.gateway_registry` |
| Production releases since v0.1.0 (2026-06-20) | **215 in 105 days** | `docs/RELEASE_NOTES.md` |
| Tests | **3,696** test functions; the full suite ran 3,640 tests on 2026-10-03 | `grep -rc "def test_"` |
| Python | **~251k lines** in `core/`, `plugins/`, `themes/`, `api/`, `morph/`, `morpheus/`, `scripts/` (~59k of it tests) | the tree |
| Templates, CSS & JS | **625** templates · **~63k** lines | the tree |
| Migrations | **251** | `*/migrations/` |
| Architecture decision records | **37** | `.torsor/architecture/decisions/` |
| `core/` imports from apps | **0 — enforced** | `scripts/check_core_boundary.py` (empty allowlist) |
| Live stores on one codebase | **3** | [below](#-three-live-stores-one-codebase) |

That release cadence is the practical proof of the architecture: every merge to `main` deploys straight to three live stores, and the boundary ratchets, disable-safety suites, and real-Postgres migration gates are what make shipping twice a day survivable.

---

## 🏪 Three live stores, one codebase

The same `main` branch deploys to all three. Each store has its own database, its own theme and its own set of enabled apps; nothing is forked.

| Store | What it sells | Theme | What it exercises |
|---|---|---|---|
| **[dotbooks.store](https://dotbooks.store)** | An independent bookshop: new and rare titles from independent presses, in print, digital and audio | `dot_books` — editorial, type-forward; cream paper, ink black, a single red dot | The book vertical end to end: print-on-demand fulfilment through Bookvault, audiobook editions, digital downloads, the 3D bookstore walkthrough, plant-a-tree at checkout |
| **[supernatural-shop.com](https://supernatural-shop.com)** | Oils, hydrosols and ritual goods — curated, modern, independent | `supernatural_shop` — light editorial; linen paper, dark ink, a single brass mark | A general catalog on the same storefront contract as the bookshop, with a different theme and app mix |
| **[montenegro-experience.me](https://montenegro-experience.me)** | Hand-picked tours, stays and hidden gems from local hosts across Montenegro | `montenegro` — Mediterranean; sea-tinted paper, Adriatic teal, sandstone accent | The `booking_marketplace` vertical: bookable experiences and stays, destination guides, hotels and an events calendar, an operator inbox for enquiries, bilingual English/Serbian with hreflang |

A fourth store starts the same way these did: `docker compose up`, then one sentence at `/dashboard/start/`.

---

## 🧠 Meet Linda — the AI operator

Morpheus has **one generalist worker**, not a zoo of specialist bots. Linda is the conversational face; the Worker is the same runtime executing autonomous jobs. Specialisation comes from *skills* — curated tool bundles — and from scopes. Never from new agent classes.

Day to day, that looks like a command bar:

```
› mark order #1042 refunded
  ⚠ refund $84.00 to Ada Whitfield — this needs your confirmation
› yes
  ✓ refunded · gift-card balance re-credited · customer emailed · audit row written

› which hardcovers are nearly out of stock?
  4 titles under 3 units — The Huguenots (1), Dune (2), …

› draft the October newsletter from last month's best sellers
  ✎ staged as a proposal — review at /dashboard/proposals/
```

Notice what happened on the first command. She did not take `confirmed=True` from her own reasoning — **consent lives in the kernel**. The refusal is recorded, a pending consent is fingerprinted against the exact arguments, and it is spent only when *your own next message* approves it. A product description or a customer note that tries to talk her into a refund gets a refusal and an audit trail, because injected text can never be a `role='user'` turn.

Since v0.65 Linda runs on **Janus**, a governed subprocess engine: the model, the step and time caps, standing instructions and the bundled store skills are merchant settings, and what she learns — notes, lessons, the skills she writes — is kept in the database, so it survives a redeploy and is shared across conversations. You read and delete it from the dashboard.

The rest of the governance, all enforced in `core/` and read from one place:

| Control | What it does |
|---|---|
| **Scopes** | Every tool declares what it needs; a caller only sees tools it may call |
| **Human approval** | High-risk writes create a server-side, single-use, argument-bound record — and fail closed if the approver is down |
| **Staged writes** | An agent can record a proposal for review instead of executing |
| **Merchant guardrails** | Kill switch, daily run and spend caps, per-action price and refund ceilings |
| **Budgets & deadlines** | One execution kernel owns them, so no tool can opt out |
| **Network egress** | Server-initiated fetches pass an SSRF gate — cloud metadata endpoints, loopback, and private ranges are refused at the socket level |
| **Audit** | Every executed call *and every denial* writes a row — the EU AI Act evidence substrate |

See [`docs/SKILLS.md`](docs/SKILLS.md) and [`AI_VISION.md`](AI_VISION.md).

---

## 🤖 Agentic commerce: be transactable by AI

An external agent should be able to discover, browse, cart, and check out — while you keep the conversion surface.

- **MCP server** — a real JSON-RPC 2.0 Model Context Protocol surface, split by audience:

  | Endpoint | Purpose |
  |---|---|
  | `POST /mcp/storefront/v1/` | catalog reads |
  | `POST /mcp/cart/v1/` | cart build |
  | `POST /mcp/checkout/v1/` | checkout build + quote *(the charge stays off MCP by design)* |
  | `POST /mcp/admin/v1/` | the operator's admin catalog (Bearer + scopes) |

  Discovery is anonymous but metered. **Executing** anything requires a Bearer token, per-token scopes, JSON-Schema validation of every argument, rate limits, a per-token approval grant for protected writes, and an audit row. A malformed or hand-edited scope value fails **closed** — never open.

- **ACP checkout** (`/acp/…`) — a conformant Agentic Commerce Protocol session: multi-item carts, live tax and shipping quotes, refusal to charge when the quote has drifted, idempotent completion under a row lock. It reuses the canonical order and money path, so there is exactly **one** implementation of totals — no chance of MCP and ACP disagreeing about what a cart costs.

- **UCP manifest** (`/.well-known/ucp.json`) — capabilities computed **live** from what is actually registered and enabled. It cannot advertise a feature you turned off. Alongside it: `/.well-known/acp.json`, `/.well-known/agent.json`, `/llms.txt`, `/ai/products.json` and `/.well-known/security.txt`.

- **Trusted agents** — when Cloudflare verifies a signed agent request (Visa Trusted Agent Protocol, Mastercard Verifiable Intent), Morpheus honours the stamped headers — but **only from a verified proxy origin**, and it fails closed by default. An unverified caller claiming to be a trusted agent is simply a stranger.

Deep dive: [`docs/MCP_SERVER.md`](docs/MCP_SERVER.md) · [`docs/AGENT_PROTOCOLS.md`](docs/AGENT_PROTOCOLS.md) · [`docs/MORPHEUS_API.md`](docs/MORPHEUS_API.md).

---

## 🔎 Found by search, and by answer engines

Most platforms treat SEO as a settings page. Morpheus treats the `<head>` as a **document the platform owns**, which is the only way it can be correct on *any* theme.

A theme calls one tag. Core seeds a document, fires a filter, and the SEO app fills in the title, description, canonical, robots directive, Open Graph, hreflang, and a single JSON-LD graph. Every entry is *keyed*, so a second writer replaces the first instead of shipping the page with two `og:type` tags and two `WebSite` nodes.

What that buys you, concretely:

- **Structured data that is a claim, not a decoration.** A property that cannot be sourced from the app that owns it is **omitted, never defaulted** — because inventing a shipping policy is a Merchant Center violation and a promise checkout will break. Shipping comes from your shipping rates, returns from your returns policy, availability from real inventory. A product sold in several editions is published as a `ProductGroup` with per-variant price and stock.
- **An index-rules engine.** One rule per query parameter, deciding whether `?sort=`, `?genre=` or a campaign tag makes a real page, a page to keep out of search, a landing page for values you choose, or an address crawlers should never fetch. Paste any URL into the dashboard and see exactly what your store publishes for it, and which rule decided.
- **Title & description templates** with a real token grammar — scoped per kind, applied only where a human hasn't typed something better. A value a merchant typed always beats a value the platform guessed, whichever table it sits in.
- **Pagination that tells the truth.** Page 2 is a page and says so; `?page=1` redirects to the clean address; a page number past the end is a 404 rather than a silent duplicate of page one.
- **Redirects 3.0.** Slug history auto-301s, 410 for the genuinely gone, regex rules, a 404 log that feeds the redirect editor.
- **AI-crawler control** — a per-bot matrix separating training crawlers from retrieval crawlers, so you can stay citable in AI answers without feeding a training run.
- **An eleven-page SEO dashboard**: overview, bulk meta, audit, 404s, redirects, index rules, templates, keywords, sitemap, structured data, site settings — and an audit that reads what the page *renders*, not what one column holds.

---

## 🛒 A tour: shoppers, merchants, developers

### What a shopper gets

- **A fast, themed storefront** on any of three shipped themes, installable as a **PWA** that works offline; page transitions and skeleton states tinted to the brand.
- **Finding things**: semantic search backed by product embeddings, personalised rails (For You, Restocked, Recently Viewed, Trending With Your Cohort, Looks Like You), a discovery quiz, lookbooks, editorial product stories, a long-form **journal** with RSS, Atom and AMP editions.
- **Product pages** with a gallery, videos, **3D and AR previews** (`.glb` for Android, `.usdz` for iOS), a flipbook preview for anything with a PDF, a sticky add-to-cart bar, trust signals (verified-buyer share, recent-purchases ticker), photo and video reviews, and — on the bookshop — a first-person **3D bookstore** you can walk around.
- **Checkout**: multi-step (shipping → payment → review) or **one-page quick checkout**; Apple Pay, Google Pay, Link and Klarna through Stripe; PayPal; cash on delivery; bank transfer. Coupons, gift cards, loyalty points and store credit all apply as tenders in the right order against tax and shipping. Live carrier rates with a lowest-carbon badge; plant a tree at checkout.
- **An account hub**: orders (with self-service cancel and return), returns with RMA tracking, addresses, downloads, points, credits, payment methods, bookings, a wishlist with shareable links, and the GDPR corner — export my data, delete my account.
- **Sign-in that doesn't need a password** (an emailed code) as well as passwords and SSO.
- **Membership and subscriptions**: plans, replenishment, curated boxes, pause / skip / swap.
- **Consent you can audit**: a cookie banner by category, Consent Mode v2 for Google, and every decision logged.

### What a merchant gets

- **A dashboard of 109 contributed pages** (Tailwind + shadcn/ui), plus a command bar that talks to Linda.
- **Orders**: lifecycle from placed to fulfilled, refunds through one service that locks the order (a double-click can never charge twice), partial refunds that re-credit gift cards, points and credit pro rata, shipped notifications with tracking, printable invoices, notes, CSV export, an *awaiting payment* queue, draft orders and quotes that convert on payment.
- **Catalog and stock**: products, variants, bundles via lookbooks, collections, metafields on anything, a unified asset manager, bulk CSV import/export, importers for Shopify, WooCommerce, Magento and BigCommerce; warehouses, stock movements, reservations, low-stock alerts and a 28-day stockout forecast.
- **Pricing and promotions**: a rule engine that stacks predicates (cart total, channel, country, customer group, product) with actions (% off, fixed off, free shipping, gift); coupons; per-market pricing and currency; B2B price lists, quotes and net terms; sandboxed merchant functions for cart totals, pricing, shipping and validation.
- **Growth**: email campaigns, newsletter with double opt-in and signup popups, abandoned-cart recovery, a post-purchase chain (tracking → delivered → review request → NPS) over email, SMS, WhatsApp and push, referrals, an affiliate platform with payouts and embeddable widgets, drops and raffles, live shopping events, A/B experiments.
- **Channels**: Google Shopping and Ads, Meta, TikTok, Pinterest, Microsoft, Snapchat, Reddit, Amazon Ads — feeds, pixels, server-side conversions and campaign reporting — with one overview of coverage, pixel state and ROAS. A multivendor **marketplace** with vendor onboarding, vendor orders and payouts.
- **Customers and CRM**: segments, a customer timeline, leads, accounts, deals and pipelines, tasks, a support inbox and chat, an account-manager agent; who signed in and when.
- **Analytics**: full-funnel, real-time, cohorts, attribution, channel ROAS, subscription analytics, GA4 + GTM with Consent Mode v2 — and Linda can be asked any of it.
- **Content**: CMS pages, blocks, menus and forms; a Notion-style journal editor with live preview and scheduled publishing; brand kit with design tokens and an AI brand-kit generator; AI content studio with a store-wide brand voice.
- **Control**: roles and permissions (six templates), staff two-factor, SSO, an audit log, notifications inbox, webhooks with retry and replay, no-code workflows, environments with snapshots and promotion, Cloudflare cache purge, backups, the error log, and **Morpheus Brain** — code quality, errors, SEO health and a daily AI advisory on one page.
- **Updates from the dashboard**: a signed release channel; *Settings → Version & updates* shows the running version against the changelog.

### What a developer gets

- **Three SDK doors** — `morpheus.app` (apps), `morpheus.core` (cross-cutting), `morpheus.theme` (themes) — and `python manage.py morph_create_plugin` to scaffold an app with its manifest, migrations and tests.
- **A contribution API instead of monkey-patching**: `StorefrontBlock` into 19 theme slots, `DashboardPage`, `SettingsPanel` (a JSON-schema form the dashboard renders for you, secrets masked), context processors, GraphQL extensions, Celery task modules, agent tools, dashboard KPIs, activity feed, health checks.
- **An event bus** with 94 typed events — `fire` for side effects, `filter` for pipelines like the cart breakdown, where the priority *is* the money order — plus a transactional outbox and HMAC-signed webhooks.
- **APIs**: Strawberry GraphQL (41 queries, 50 mutations; the stable public API, with a response cache that varies correctly), DRF REST under `/v1/`, four MCP servers, ACP, agent invocation over REST with streaming.
- **Themes** that sign a head contract and render contributed blocks; the storefront consumes GraphQL, never the ORM, so a headless front end gets the same data ([`docs/HEADLESS.md`](docs/HEADLESS.md)).
- **A test suite that proves the architecture**: disable-safety suites toggle every app off and GET every page; slot-parity tests fail when a block has no slot; a real-Postgres migration job; a celery-wiring test that boots a fresh interpreter the way the worker does; guards that are mutation-tested before they ship.
- **CI ratchets** for the core boundary (0, enforced) and the app boundary (declared dependencies only; the baseline can only shrink), `ruff`, `bandit`, `pip-audit`, `release --check`.
- **Docs that ship with the code**: 30 guides, 102 dated plans, 37 ADRs, a per-release changelog and a migration guide for out-of-tree apps.

---

## 🧱 Architecture: a small kernel, a deep ecosystem

**Powerful *through* modularity, not by bloating the core.** The kernel is the mechanism that keeps a deep commerce engine swappable, disable-safe, and legible to an agent.

```
                         ┌────────────────────────────────────────┐
   Shoppers · Staff ·    │            Entry surfaces              │
   AI agents · Webhooks  │  Storefront · Dashboard · GraphQL ·    │
        │                │  REST · MCP · ACP · Assistant · Tasks  │
        ▼                └───────────────────┬────────────────────┘
                                             ▼
                    ┌────────────────────────────────────────────┐
                    │   core/  (the kernel — never commerce code) │
                    │  auth · hooks bus · settings · request      │
                    │  lifecycle · i18n · observability · agents  │
                    │  runtime · safety boundary · self-improve   │
                    └───────────────────┬────────────────────────┘
                                        │  hooks (fire/filter) + contribution APIs
             ┌──────────────┬───────────┼───────────┬──────────────┐
             ▼              ▼           ▼           ▼              ▼
        catalog        orders      payments     agent_mcp    …105 more apps
         (an app)     (an app)     (an app)      (an app)   in plugins/installed/
```

**What lives in `core/`:** only what is genuinely foundational — auth and the sign-in log, the event bus, settings, request lifecycle, the i18n kernel, observability and the error pipeline, the agent runtime, the safety boundary (`core/safety.py`, the single source of truth for what AI may touch), and the self-improvement loop. Nothing else.

A CI ratchet (`scripts/check_core_boundary.py`) enforces that `core/` imports **zero** apps. Not "few". Zero — the allowlist is empty and a single new leak fails the build. A sibling ratchet stops apps importing each other except through declared dependencies and hooks, and its baseline can only ever shrink.

**Core fires, apps answer.** When the dashboard needs to know whether you may refund an order, it doesn't import the permissions app — it fires a capability check and whoever owns permissions answers. Same inversion for pricing rules, structured data, robots directives, health checks and the storefront head. That one pattern is why an app can be disabled without leaving a hole.

**Three SDK doors** curate the common imports:

| Door | For | Exposes |
|---|---|---|
| `morpheus.app` | app authors | `Plugin`, `StorefrontBlock`, `DashboardPage`, `SettingsPanel`, `.views/.models/.forms` |
| `morpheus.core` | cross-cutting | `events`, `hooks`, `tool`, `ToolResult`, `record_ai_decision`, `Money`, … |
| `morpheus.theme` | theme authors | the storefront slot contract |

More: [`ARCHITECTURE.md`](ARCHITECTURE.md) · [`docs/PLUGIN_DEVELOPMENT.md`](docs/PLUGIN_DEVELOPMENT.md) · [`CHARTER.md`](CHARTER.md).

---

## 🧩 What's in the box: all 109 apps

Every shipped capability is a toggleable app, and every app below is described from its own manifest at v0.76.0. The always-current version is **Settings → About Morpheus** in the dashboard; the source of truth for the count is `MORPHEUS_DEFAULT_APPS` in `morph/settings.py`.

> **Apps and plugins are the same thing.** "App" is the word the product uses — in the dashboard, in these docs, and at every seam you touch as an author (`app.py`, `morpheus.app`, `app_registry`). Two things still read "plugin" on purpose: the directory `plugins/installed/` and the base class `MorpheusPlugin`, because renaming them would rewrite roughly two thousand import paths for no user-visible gain. Upgrading an out-of-tree app: [`docs/MIGRATING.md`](docs/MIGRATING.md).

<details open>
<summary><strong>Commerce core</strong> — 12 apps</summary>

| App | What it does |
|---|---|
| `catalog` | Products, variants, categories, collections and attributes; every displayed and charged price flows through one price seam |
| `orders` | Cart, the order lifecycle, fulfilment, refunds through one locking service, transactional email, invoices, notes and CSV export |
| `customers` | Accounts, addresses, passwordless and password sign-in, the self-service account hub |
| `inventory` | Warehouses, stock levels and movements, low-stock alerts, atomic reservations, a stockout forecast |
| `payments` | The payment engine: Stripe (Payment Element, webhooks, refunds), PayPal, bank transfer; a gateway without credentials is never offered |
| `advanced_payments` | Cash on delivery and a staff-only sandbox "test payment", as modular gateways |
| `checkout_experience` | One-page and express checkout: Apple Pay, Google Pay, Link, Klarna, address autocomplete, motion-reduced variant |
| `shipping` | Zones and rates: flat, weight tiers, order-total tiers, free over a threshold; Shippo / EasyPost adapters |
| `smart_shipping` | Live carrier rates at checkout (EasyPost, Shippo) with a per-rate carbon estimate and a lowest-carbon badge |
| `tax` | Regions and categorised rates: VAT, US sales tax, EU OSS; computed from the shipping address; Stripe Tax adapter |
| `draft_orders` | Staff-built draft orders and quotes, shared with the customer, converted to a real order on payment |
| `one_click` | One-tap returning-shopper checkout with rotating AES-GCM device tokens |

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
<summary><strong>Merchandising & personalisation</strong> — 8 apps</summary>

| App | What it does |
|---|---|
| `dynamics` | Personalised merchandising blocks (for-you, related, recently viewed, bought-together) configured per theme slot, with an autopilot that proposes layouts |
| `rails` | Five feed-style rails: For You, Restocked, Recently Viewed, Trending With Your Cohort, Looks Like You; anonymous trending without consent |
| `personalisation` | Co-purchase recommendations and propensity-ordered product lists, all consent-gated |
| `discovery_quiz` | A zero-party-data quiz that ends in a personalised category view and feeds segmentation with consent |
| `lookbook` | Editorial product bundles with their own pages, added to cart as one line or as individual products; AI auto-looks from the co-purchase graph |
| `drops` | Scheduled drops, raffle-by-waitlist for limited stock, push notifications, a stock-equalising queue, post-sellout waitlists |
| `experiments` | In-process A/B tests with cookie-stable assignment and Wald-interval significance |
| `metafields` | Schema-less custom fields on any record — products, customers, orders, pages |

</details>

<details>
<summary><strong>Storefront & content</strong> — 19 apps</summary>

| App | What it does |
|---|---|
| `storefront` | The theme-powered storefront; it consumes the GraphQL API internally and never touches the ORM |
| `cms` | Pages, reusable blocks, named menus and merchant-defined forms, all theme-overridable |
| `journal` | A Notion-style block editor with live preview and scheduled publishing; text, image, video, product, collection and form blocks; RSS, Atom and AMP |
| `richtext` | A self-hosted Lexical rich-text editor used by the product and page forms; no CDN, no build step at deploy |
| `media` | A unified asset manager for images, video, audio, PDFs, spreadsheets, documents and digital downloads |
| `brand_kit` | Design tokens (colours, fonts, spacing, radii) as CSS variables, plus an AI brand-kit generator that reads your hero imagery |
| `product_gallery` | Cover plus square slider on product pages, native scroll-snap, no JS dependency |
| `product_stories` | Scroll-snap "why you'll love it" story blocks, ordered per product, edited in the dashboard |
| `product_videos` | YouTube, Vimeo or raw embeds on the product page |
| `media_3d` | Per-product 3D and AR previews (`.glb` for Android, `.usdz` for iOS) with a size budget, paired with shoppable video |
| `bookstore_3d` | A first-person 3D walkthrough with real catalog products on the shelves (three.js, no build step) |
| `immersive_pdp` | A sticky, theme-styled add-to-cart bar with an edition picker and quantity |
| `flipbook` | A 3D page-flipping preview for any product with a PDF attached |
| `webstories` | Google-indexable AMP Web Stories generated from product images, embedded on the product page |
| `live_commerce` | Scheduled live shopping events: embedded stream, pinned buyable products, UTM-attributed conversion, replay |
| `pwa` | An installable, offline-capable storefront: manifest, service worker, icons |
| `motion` | Page transitions, scroll-snap story progress, button micro-feel and skeleton states, tinted to the brand |
| `trust_signals` | Star rating, verified-buyer percentage and a recent-purchases ticker on the product page |
| `advanced_ecommerce` | Recently-viewed, free-shipping progress and low-stock badges on the storefront; bulk price edit and low-stock alerts in the dashboard |

</details>

<details>
<summary><strong>CRM, retention & growth</strong> — 13 apps</summary>

| App | What it does |
|---|---|
| `crm` | Leads, accounts, deals and pipelines, an interactions timeline, follow-up tasks, customer notes, a support inbox and chat, and an account-manager agent |
| `reviews` | Customer reviews on the product page with merchant moderation |
| `ugc_reviews` | Photo and video reviews with auto-moderation and a creator tier; approved UGC surfaces in the gallery and home rail |
| `wishlist` | Saved items for customers and guests, shareable links, agent tools for the concierge |
| `save_for_later` | Save-for-later from the cart, price-drop and back-in-stock notifications, shareable gift wishlists |
| `cart_abandonment` | Detects stale carts and runs the consent-checked, multi-step recovery email drip |
| `post_purchase` | The automated chain: shipment tracking → delivered confirmation → review request → NPS survey |
| `rich_post_purchase` | The same chain over email, SMS, WhatsApp and push, with per-step channel choice and rich content blocks |
| `post_checkout_upsell` | One suggested product on the order confirmation page |
| `newsletter` | Signup popups and a double-opt-in subscriber list; sends reuse the campaign engine |
| `referrals` | Give-5 / Get-5 referrals, paid in store credit, with an optional contest layer |
| `affiliates` | Affiliate links, attribution, conversions, commission tiers, payouts, embeddable shop widgets |
| `returns_portal` | Exchange or store credit as first-class return resolutions, with feedback routed to the CRM |

</details>

<details>
<summary><strong>Sales channels & marketplaces</strong> — 10 apps</summary>

| App | What it does |
|---|---|
| `channels` | One operator view of every channel: connection status, feed coverage, pixel state and ROAS |
| `google_shopping` | The Merchant Center feed with a coverage dashboard, plus Google Ads conversions and reporting |
| `meta_commerce` | Facebook and Instagram catalog feed and API push, the Meta Pixel and Conversions API, campaign reporting |
| `tiktok_commerce` | TikTok catalog feed, Pixel and Events API, campaign reporting and management |
| `pinterest_commerce` | Pinterest catalog feed, the Tag and Conversions API, the Ads API |
| `microsoft_commerce` | Microsoft Merchant Center feed and the UET conversion tag |
| `snapchat_commerce` | Snapchat catalog feed, the Snap Pixel and Conversions API, campaign reporting |
| `reddit_ads` | The Reddit Pixel, Conversions API and Ads API |
| `amazon_ads` | Sponsored Products campaign management and performance reporting over the Amazon Ads API |
| `marketplace` | Multivendor: vendor onboarding and applications, vendor orders, payouts, reports |

</details>

<details>
<summary><strong>AI & agents</strong> — 11 apps</summary>

| App | What it does |
|---|---|
| `agent_core` | Linda's tool catalogue — catalog reads and writes, order ops, inventory, content, analytics — and the kernel runtime shared by sub-agents |
| `agent_mcp` | The agent gateway: four MCP servers, the UCP discovery manifest, trusted-agent middleware, API tokens with scopes |
| `agentic_checkout` | Agentic Commerce Protocol checkout sessions and a product feed for AI buyers such as ChatGPT Instant Checkout (opt-in) |
| `ai_assistant` | Product embeddings, semantic search, recommendations, dynamic pricing and AI-provider configuration |
| `ai_content` | The store-wide brand voice every AI generation reads, product-description generation, the content and assets studio |
| `ai_stylist` | A conversational shopping assistant on the storefront, with a shopper-facing persona and its own audit trail |
| `janus` | The engine behind Linda: on/off, model, step and time caps, standing instructions, bundled skills, and what she has learned |
| `linda_generated` | The landing zone for tools Linda writes herself, filled only through the gated apply pipeline |
| `morpheus_brain` | One console for code quality, errors, SEO health and daily industry reports, with an AI advisory briefing on the whole site |
| `store_bootstrap` | Type one sentence; get a brand voice, a category tree and a starter catalogue |
| `lumina` | The Lumina book-creator landing page: write with AI and voice, auto-translate, sell on the bookshop |

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
<summary><strong>Operations, security & compliance</strong> — 19 apps</summary>

| App | What it does |
|---|---|
| `admin_dashboard` | The merchant dashboard (Tailwind CSS + shadcn/ui), host to every contributed page and settings panel |
| `rbac` | Roles and permissions: six role templates, 32 capabilities, bindings optionally scoped per channel, `log` → `enforce` per store |
| `staff_mfa` | A TOTP second factor for staff: authenticator enrolment, recovery codes, required-for-staff mode, an audited break-glass reset |
| `staff_sso` | OIDC / SAML 2.0 staff sign-in (Okta, Entra, Google Workspace) with JIT provisioning and domain or group gating |
| `gdpr` | Article 15 export and Article 17 erasure as self-service, an auditable request trail, seeded Privacy / Terms / Imprint pages |
| `consent` | A cookie banner with per-category opt-in and an auditable log of every decision |
| `fraud_rules` | Risk scoring over Stripe Radar: velocity, address mismatch, BIN denylist, refund history |
| `observability` | The audit-log surface, the error log, per-merchant metric rollups |
| `backups` | Nightly database and media backups with retention, scheduled through beat |
| `webhooks_ui` | Webhook endpoints, HMAC-SHA256-signed deliveries, a delivery log with retry and replay |
| `notifications_center` | A persistent staff inbox for what needs follow-up: pending RMAs, low stock, failed agent runs, overdue tasks |
| `workflows` | No-code automation: a trigger, a condition, one or more actions — including "run an agent skill" |
| `functions` | Sandboxed merchant-defined functions for cart totals, product pricing, shipping rates and order validation |
| `cloudflare` | Cache purge on product and collection changes, DNS integration |
| `environments` | Dev / staging / production environments with snapshots and promotion |
| `importers` | Idempotent migration from Shopify, WooCommerce, Magento and BigCommerce, plus bulk CSV import and export |
| `feature_adoption` | Per-install feature-usage aggregates and an install-health score, with no PII |
| `feedback` | Staff bug reports with a screen capture and the recent JavaScript errors attached, as tickets under Settings |
| `release_notes` | Settings → About Morpheus (a live catalogue of every installed app) and Version & updates |

</details>

<details>
<summary><strong>Verticals</strong> — 6 apps</summary>

| App | What it does |
|---|---|
| `book_product` | Books as a first-class product type: author, format and paper, page count, a cover-PDF 3D preview, genres, series and taxonomies |
| `audiobooks` | A priced audiobook edition with a modal player on the product page; ElevenLabs narration |
| `bookvault` | Print-on-demand fulfilment through Bookvault: live shipping quotes at checkout, paid orders sent automatically, a bulk product linker |
| `eco_impact` | A book's paper, wood and CO₂ footprint on its page, and plant-a-tree at checkout, tracked as a fund |
| `digital_products` | Token-protected downloads with expiry and count limits, emailed automatically after payment |
| `booking_marketplace` | Bookable experiences and stays from local hosts, destination guides, hotels and an events calendar, with an operator inbox (opt-in; runs the Montenegro store) |

</details>

> **Before adding an app:** audit for overlap and justify the boundary. *One concept, one owner.* A previous release shipped a second, incompatible returns table that was invisible to the dashboard, to return numbers, and to the refund service. The rule exists because ignoring it cost a release.

---

## 🔁 It runs itself

A store you own is only a bargain if it doesn't need you at 3 a.m. Morpheus watches itself and tells you only when something needs a human:

- **A nightly health check** (05:00 UTC) proves each store can still sell: a payment method is offered, a real product can be carted and priced inside a rolled-back transaction, the home, product, cart and checkout pages load through the CDN, outgoing email is set up and the order-email templates load. Any app that can stop the store selling contributes its own check. A failure is recorded and emailed at once.
- **A daily error digest** (06:30 UTC) groups the last 24 hours of server errors by cause. Nothing is sent on a clean day. Every 500 and every client-side JavaScript error is captured, fingerprinted and kept across deploys; the log prunes itself after 30 days.
- **Nightly backups** of database and media with retention; a sign-in log (who, when, from where, on what) that prunes itself after 90 days because IP addresses are personal data; a transactional outbox for when you add a message broker.
- **57 scheduled jobs** — rollups, forecasts, feed refreshes, cart-recovery drips, the update check, the morning briefing — all declared where the scheduler reads them, with a test that fails if a core job goes missing.
- **Health endpoints** (`/healthz`, `/readyz` with the running version, `/healthz/deep`) and a deploy-smoke workflow that fails red if production never converges on the version you pushed.
- **Signed updates**: release manifests are Ed25519-signed and verification fails closed; the per-app and per-theme channel refuses anything whose bytes don't match the signed checksum.
- **Every deploy is versioned.** `python manage.py release` bumps the version and writes the dated changelog entry atomically; a forgotten bump fails the gate before it can become a mystery in production.

---

## ♻ The self-improvement loop

The immune system of a platform built with heavy AI assistance — and the one thing that cannot be a toggleable app, so it lives in `core/`:

1. **Autonomic engine** — Linda proposes code and content improvements.
2. **Code-quality scanner** — catches regressions and drift before they compound.
3. **Upstream-drift tracking** — watches dependencies moving underneath you.
4. **LLM consensus review** — a panel of independent models judges each proposed change before a human ever sees it.
5. **Human gate** — you approve. Machines never merge alone.

Underneath it, **hooks are the enforcement layer**: rules in a Markdown file are advisory and a model can ignore them, so the ones that matter run as PostToolUse hooks — `ruff`, forbidden-import checks, migration guards — on every single AI edit. CI applies every migration against real Postgres, because SQLite will happily accept a schema change that takes production down.

---

## 🔒 Safety, security & compliance

- **Safety boundary** — `core/safety.py` is the single source of truth for what AI may touch, read by the self-improvement loop, the MCP server, CI hooks, and pre-commit. An app may *add* protection in its own manifest but never remove it.
- **Authorization is one seam.** Staff go through RBAC capabilities (`core/authz.py`, 249 gated views and the GraphQL surface on the same vocabulary); agents go through per-token scopes. A role revoked in the dashboard reaches the API, because the API asks the same question. The seam fails *open* on absence by design: an authorization layer that locked every merchant out of their own dashboard when its answerer was missing would be a worse bug than the one it prevents. Denial is opt-in per store (`off` → `log` → `enforce`), so you audit what *would* be denied before anything is.
- **Consent lives in the kernel.** No tool argument an LLM can write counts as a human's yes; approval is spent only by the human's own next message, bound to the exact arguments, single-use.
- **Token scopes fail closed.** A missing scope key on a legacy token inherits wildcard for back-compat — but a present-and-malformed value, a half-failed token resolution, or a dashboard round-trip can never silently promote a token to full access. A Bearer token is judged by its **own** scope set, never by the staff service user it resolves to.
- **SSRF egress gate** — `core/net.py` screens every server-initiated fetch (webhook deliveries, media downloads): cloud metadata endpoints, loopback, and private ranges are refused; DNS failures are treated as transient so a resolver blip can't permanently kill a queued webhook.
- **Tool names are a stable API.** The agent-tool registry is first-owner-wins and raises on a cross-app name collision under tests — so a gated write tool can never be silently shadowed by an ungated twin.
- **Staff MFA & SSO** — second factor and SSO ship as apps, with a guard ensuring no new sign-in path can quietly bypass MFA, and a sign-in log the owner can read per person.
- **Money correctness** — one price seam for displayed *and* charged prices; refunds through one locking service; tenders (gift cards, points, store credit) re-credited pro rata on refund; entitlements gated on evidence the money moved, never on a status string; stock reservations that expire.
- **GDPR & consent** — data-subject flows, consent-gated analytics, Consent Mode v2.
- **EU AI Act** — Article 50 disclosure for synthetic content, plus a dated evidence export of the decision and approval trail.
- **Supply chain** — hash-pinned `requirements.lock.txt`, `pip-audit` and `bandit` in CI, Dependabot on.
- **Signed updates** — release manifests are Ed25519-signed and verification **fails closed**; an update whose bytes do not match its signed checksum is refused before it is ever unpacked.

See [`SECURITY.md`](SECURITY.md) · [`docs/COMPLIANCE.md`](docs/COMPLIANCE.md).

---

## 🧭 Roadmap

Two documents drive the plan, and they deliberately disagree: [`docs/product_roadmap_2026.md`](docs/product_roadmap_2026.md) is the **strategy** (benchmarked against Shopify Plus, Adobe Commerce, BigCommerce, VTEX and the agentic-commerce shift), and [`docs/plans/roadmap-2026-execution.md`](docs/plans/roadmap-2026-execution.md) is the **fact-checked execution plan** — what actually exists in the tree, what is genuinely missing, and the build order. Where they conflict, the fact-check wins; more than one "6–8 week Q3 build" in the strategy document turned out to already be shipping.

### Shipped — the story so far (2026)

| Arc | Releases | What landed |
|---|---|---|
| **Bootstrap** | v0.1–v0.15 · June–July | Store-in-a-sentence provisioning, dashboard, catalog → cart → checkout → fulfilment, the dot_books theme, live production store |
| **Agent governance (Horizon 1)** | v0.22–v0.32 · July | Consent kernel, agent auth hardening, EU AI Act Art. 50 disclosure, `agents.md`, real MCP cart/checkout, AI-Act evidence export, merchant guardrails (kill switch, spend caps, price/refund ceilings) |
| **Boundary ratchet to zero** | v0.27 · July | `core/` imports **nothing** from apps — allowlist empty, enforced empty ever since |
| **Three-SDK split** | v0.33–v0.34 · July | `morpheus.{app, core, theme}` doors; all 108 apps / 382 files migrated in one release |
| **Money-path correctness** | v0.36–v0.40 · Aug | Tender re-credit on refunds, one price seam for displayed *and* charged prices, evidence-based entitlements, stock-reservation expiry |
| **Platform trust** | v0.41–v0.45 · Aug | Dead-switch repair (maintenance mode, brand tokens, store identity), apps unification, the RBAC seam, the Ed25519-signed update channel, the disable-safety sweep |
| **SEO 3.0** | v0.46–v0.54 · Aug | Theme-agnostic head document, `SeoMeta` single ownership, redirects 3.0 (auto-301 slug history, 410, regex), title/description template grammar, index-rules engine, 2026-grade structured data |
| **Security hardening campaign** | v0.55–v0.61 · Aug–Sep | Five reachable holes closed: any-Bearer-token-was-admin, MCP scopes failing open, cart IDOR, the selfdev self-coding bypass, webhook SSRF to cloud metadata. Plus: first-owner-wins tool registry, discovery metering + argument validation, cache vary-keys, RBAC coverage 43 → 249 views, GraphQL wired to the capability seam, the outbound SSRF gate |
| **Agent engine & second-store proof** | v0.62–v0.74 · Sep | Linda's runtime moved onto **Janus** (a governed subprocess engine with database-durable learning that survives a redeploy), an agent-quality pass that took a live eval from 5-of-11 timeouts to 11-of-11, and the platform proving itself on **two more live stores** on the same codebase — the Montenegro travel marketplace (`booking_marketplace` vertical, bilingual SEO) and the Supernatural shop — alongside a run of storefront, SEO and structured-data hardening |
| **Commerce stability & self-monitoring** | v0.75–v0.76 · Sep–Oct | A whole-flow audit of the purchase spine turned into five releases: a payment method is offered only when it can charge, tax from the shipping address, order emails that had never rendered, shipped notifications, refunds through one locking service, invoices and order export, store credit as a tender, guest orders linked on a *verified* email, drafts on the real order path, inert apps retired; then a nightly health check, a daily error digest, core's scheduled jobs (which had never run) fixed, and the sign-in log |

The full dated record — all 215 entries — is [`docs/RELEASE_NOTES.md`](docs/RELEASE_NOTES.md); every deploy is required by CI to add one.

### Now — Q4 2026

| Work | Status | Notes |
|---|---|---|
| **Online payments live on the reference stores** | waiting on credentials | Stripe and PayPal are wired and gated; the stores sell on cash on delivery until their accounts are set up, and a local card processor is next |
| **RBAC `enforce` flip readiness** | in progress | Coverage and GraphQL wiring are done; what remains is operational — provision role bindings, run a week of `log`-mode traffic, confirm zero would-deny warnings, then flip. Deliberately a human decision. |
| **Agent execution boundaries, remainder** | next up | The SSRF egress gate shipped; still open: a per-run wall-clock at the runtime level, an agent/read-only database role in `core/db_router.py`, and process/container isolation for the sandbox |
| **SEO 3.0 phase 3** | specified | Audit engine, an issues queue with one-click fixes, the rebuilt SEO dashboard IA |

### Next

| Work | Why it's next |
|---|---|
| **B2B procurement depth** | The largest genuinely-absent roadmap item. Price lists, quotes with a 7-state lifecycle, and net terms already ship; missing are buyer-initiated **RFQ intake**, **multi-level approval chains**, **requisition lists**, **company/buyer hierarchy**, and **sales-rep impersonation** — the last is security-sensitive by nature, which is exactly why it waited for the RBAC work to land first |
| **Bundles and manual capture** | Real product bundles on the price seam; manual and fulfilment-triggered payment capture |
| **AI merchandising bulk-content UI** | The Thompson-sampling bandit and the AI merchandiser autopilot already ship; the gap is narrow — a dashboard bulk-action surface over the existing bulk catalog services, and the bandit → layout-suggestion linkage |
| **SEO engines** | Search Console (OAuth), Bing Webmaster, IndexNow submission, CrUX/PSI — the in-app search-performance data the dashboard is already shaped for |
| **Web Bot Auth (RFC 9421)** | Signed-agent verification beyond the Cloudflare-verified path |
| **Multi-storefront** | Several storefronts from one install (approved as ADR 0018) |

### Later — 2027

| Work | Honest current state |
|---|---|
| **Dynamic pricing & predictive inventory** | Today: a deterministic rules engine on the price seam and a 28-day moving-average stockout forecast. The 180-day horizon needs seasonality, which needs historical depth — genuinely a later phase, not a sprint |
| **Headless reference storefront (Next.js)** | The GraphQL surface is documented ([`docs/HEADLESS.md`](docs/HEADLESS.md)); the reference app serves developer adoption rather than merchants, so it queues behind merchant-facing work |
| **SEO 3.0 phases 5–7** | Site crawler, the staged-AI content layer, and ownership cleanups (image pipeline → media) |

> **A note on how this roadmap is maintained.** It was fact-checked against the tree before a line of it was built — which found that the UCP integration estimated at 6–8 weeks already shipped, and that two of three named debt blockers were already resolved. Roadmaps here are treated like code: wrong premises get patched in the same commit as the work that disproved them.

---

## 🧾 What this is not (yet)

A README that only lists wins is a sales page. Here is the honest edge of the thing, because you will find it anyway on day two:

- **This is a 0.x project.** It runs three real stores in production and ships most days, but the version number means what it says.
- **Card payments are wired, not yet battle-tested.** Stripe and PayPal are integrated and gated so a store never offers a method it can't charge, but the reference stores currently sell on cash on delivery and the Stripe card-collection leg has not yet been run against a live Stripe account.
- **Some surfaces are deeper than others.** Core commerce, the agent layer, security, and SEO have had the most attention. Search Console integration, the site crawler and bulk AI content tooling are specified and not yet built.
- **A few screens are still ahead of their data.** Keyword tracking, for instance, has a page but nothing yet writes positions into it — it is waiting on the Search Console work.
- **RBAC ships in log mode by default.** The capability checks run everywhere and record what they *would* deny; flipping a store to `enforce` is a deliberate per-store step after its role bindings exist. That default is honest, not timid — an enforcement flip with no bindings provisioned would lock out every non-superuser on day one.
- **It is not open source — yet.** The code is public under the Business Source License 1.1: free to read, evaluate, develop and test; production use needs a commercial licence; each version turns Apache 2.0 four years after it is released. Versions up to v0.76.0 were published under Apache 2.0 and stay that way.
- **It is opinionated to the point of being bossy.** One AI worker, not many. Everything is an app. Core imports nothing. If you disagree with those, you will be fighting the grain of the codebase rather than riding it.

The full, dated list of what shipped and when is in [`docs/RELEASE_NOTES.md`](docs/RELEASE_NOTES.md), and the breaking changes are in [`docs/MIGRATING.md`](docs/MIGRATING.md). Both are maintained because a deploy without a changelog entry fails CI.

---

## 🛠 Tech stack

- **Django 6** (Python 3.12) · **PostgreSQL** · **Redis** · **Celery** (+ beat)
- **Strawberry GraphQL** (the stable public API) + **DRF** for REST
- **djmoney** for multi-currency money · **allauth** for auth and SSO · passwordless email-code sign-in in core
- **Tailwind + shadcn/ui** dashboard · a self-hosted **Lexical** editor · **three.js** for 3D · AMP for stories
- **MCP / ACP / UCP** agent protocols · any OpenAI-compatible LLM provider, configured in the dashboard
- Container-first (`Dockerfile`, `docker-compose.yml`, Kubernetes manifests); the reference deployment runs behind **Cloudflare → Plesk → Coolify (Traefik)**

---

## 🚀 Quick start

### Option A — Docker (the full stack: Postgres, Redis, worker, beat)

```bash
git clone https://github.com/magnetoid/Morpheus.git
cd Morpheus
docker compose up -d
```

The `web` service migrates on boot. Open **http://localhost:8000/dashboard/**, create the first account, and then bootstrap a store from a single sentence at **/dashboard/start/**.

### Option B — No Docker (SQLite, synchronous paths only)

```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

> Background work (`.delay()`) needs Redis and Celery, so plain `runserver` covers request/response but not scheduled or queued jobs. Use the compose stack for the full experience. Details in [`docs/QUICK_START.md`](docs/QUICK_START.md).

### Run the tests

```bash
# Always pin an in-memory DB — a bare `manage.py test` tries to reach the Docker `db` host.
DATABASE_URL='sqlite:///:memory:' python manage.py test plugins.installed.<name>
```

### Rather not run it yourself?

That is what [Get in touch](#-get-in-touch) is for.

---

## 📁 Project structure

```
Morpheus/
├── core/                      # the kernel: auth + sign-in log, hooks, agent runtime, safety, errors, self-improvement
│   ├── agents/                # agent runtime, tool registry, guardrails, approvals
│   ├── assistant/             # Linda's conversational runtime and the Janus engine
│   ├── errors/                # error capture, the daily digest, the nightly health check
│   ├── authz.py               # the RBAC capability seam (core fires, the rbac app answers)
│   ├── hooks.py               # the fire/filter event bus (all cross-app coupling goes here)
│   ├── net.py                 # the SSRF egress gate for server-initiated fetches
│   └── safety.py              # single source of truth for what AI may touch
├── morph/                     # Django project: settings, root urls, MORPHEUS_DEFAULT_APPS, the beat schedule
├── morpheus/                  # the three SDK doors: {app, core, theme}
├── plugins/installed/<name>/  # every feature — app.py, apps.py, models, migrations, templates, tests
├── themes/                    # storefront themes: dot_books, supernatural_shop, montenegro
├── api/                       # GraphQL view + hardening (permissions, response cache, vary keys)
├── scripts/                   # CI ratchets (core boundary, app boundary, API stability, release)
├── docs/                      # architecture, app development, MCP, API, compliance, runbooks, plans
└── docker-compose.yml         # the full local stack
```

---

## 🧰 Development workflow

Morpheus is built for AI-assisted development with hard guardrails. The house rules live in [`CLAUDE.md`](CLAUDE.md) and [`AGENTS.md`](AGENTS.md), and they are mostly a record of things that went wrong once:

- **One concept, one owner.** Extend another app with a foreign key and hooks, never a parallel table.
- **Add a migration before merge.** A model without one fails the system check on every production boot, and CI applies every migration against real Postgres.
- **Ship code and docs together.** A change to architecture, a convention, or a public contract updates the matching Markdown in the same commit — not "later".
- **Every deploy bumps the version.** `python manage.py release --minor "Headline" -m "bullet"` updates the version and prepends a dated release-notes entry atomically. `release --check` is a blocking gate.
- **Verify for real.** A green lint and type check is necessary, not sufficient. Smoke the actual behaviour, then smoke it again on the live URL.

There is a fifth rule that is really the other four combined: **a passing test proves only what it asserts.** New guards here are mutation-tested — the guard is deliberately broken to confirm a test actually fails. More than one test in this repo has been caught passing for entirely the wrong reason.

---

## 🗂 Project memory: torsor-helper

Morpheus is built with heavy AI assistance, so it carries a durable, retrievable project brain that survives across sessions and keeps architectural decisions from being re-litigated every time context resets. That brain is **torsor-helper** (adopted in ADR 0001), under [`.torsor/`](.torsor/):

| Area | What it holds |
|---|---|
| `charter.md` | the product charter — the non-negotiable laws |
| `architecture/system-patterns.md` · `tech-context.md` | recurring patterns, and the stack and runtime context |
| `architecture/decisions/` | the ADRs — every load-bearing decision, currently 37 of them |
| `map/` | a compiled map of the repo's modules |
| `memory/journal` | an indexed decision and observation journal |
| `active/context.md` · `progress.md` | the current working context and in-flight progress |

The knowledge base is semantically indexed (fastembed `bge-small`, hybrid retrieval with recency and graph boosting) and reached through an MCP server with token budgets, so context stays cheap. In practice a session starts by pulling the charter, the rules and the active context as a compact primer — so an agent works *with* the platform's laws instead of rediscovering them, badly, for the fourth time.

---

## 🌐 Deployment

**Merging to `main` is a production deploy.** Coolify watches the repo and builds on every push; there is no separate ship step. So:

- Every merge **must** bump the version and add a release-notes entry — Settings → *Version & updates* reads both, and an unversioned deploy ships changes nobody can see in the changelog.
- `/readyz` reports the live version and health, and a smoke workflow confirms production actually converges on the version you pushed.
- Batch local commits into one deploy. Rapid merges thrash the builder.
- One push, three stores: each Coolify app points at the same repository with its own database, environment and enabled apps.

Guides: [`docs/deploy-coolify.md`](docs/deploy-coolify.md) · [`docs/deploy-plesk-nginx.md`](docs/deploy-plesk-nginx.md) · recovery procedures in [`docs/OPERATIONS_RUNBOOK.md`](docs/OPERATIONS_RUNBOOK.md).

---

## 📚 Documentation

| Topic | Doc |
|---|---|
| System architecture & request lifecycle | [`ARCHITECTURE.md`](ARCHITECTURE.md) · [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) |
| Product charter & principles | [`CHARTER.md`](CHARTER.md) · [`AI_VISION.md`](AI_VISION.md) |
| Roadmap — strategy & fact-checked execution | [`docs/product_roadmap_2026.md`](docs/product_roadmap_2026.md) · [`docs/plans/roadmap-2026-execution.md`](docs/plans/roadmap-2026-execution.md) |
| Building an app | [`docs/PLUGIN_DEVELOPMENT.md`](docs/PLUGIN_DEVELOPMENT.md) |
| Building a theme | [`docs/THEME_DEVELOPMENT.md`](docs/THEME_DEVELOPMENT.md) · [`docs/THEME_EXTENSIONS.md`](docs/THEME_EXTENSIONS.md) |
| Public API (GraphQL / REST) | [`docs/MORPHEUS_API.md`](docs/MORPHEUS_API.md) · [`docs/API_STABILITY.md`](docs/API_STABILITY.md) |
| Agent protocols (MCP / ACP / UCP) | [`docs/MCP_SERVER.md`](docs/MCP_SERVER.md) · [`docs/AGENT_PROTOCOLS.md`](docs/AGENT_PROTOCOLS.md) |
| AI skills | [`docs/SKILLS.md`](docs/SKILLS.md) |
| Compliance (GDPR / EU AI Act) | [`docs/COMPLIANCE.md`](docs/COMPLIANCE.md) |
| Headless usage | [`docs/HEADLESS.md`](docs/HEADLESS.md) |
| Webhooks | [`docs/WEBHOOK_RECIPES.md`](docs/WEBHOOK_RECIPES.md) |
| Sales-channel setup | [`docs/google-shopping-setup.md`](docs/google-shopping-setup.md) · [`docs/meta-commerce-setup.md`](docs/meta-commerce-setup.md) · [`docs/pinterest-tiktok-setup.md`](docs/pinterest-tiktok-setup.md) |
| Operations & incident recovery | [`docs/OPERATIONS_RUNBOOK.md`](docs/OPERATIONS_RUNBOOK.md) · [`docs/PERFORMANCE.md`](docs/PERFORMANCE.md) |
| Going live: payments, email, keys | [`docs/REVENUE_PATH.md`](docs/REVENUE_PATH.md) |
| Accessibility & UI style | [`docs/accessibility.md`](docs/accessibility.md) · [`docs/UI_STYLE_GUIDE.md`](docs/UI_STYLE_GUIDE.md) |
| House rules for AI-assisted work | [`CLAUDE.md`](CLAUDE.md) · [`AGENTS.md`](AGENTS.md) · [`RULES.md`](RULES.md) |
| Updating a deployment | [`docs/UPDATING.md`](docs/UPDATING.md) |
| Upgrading across a breaking change | [`docs/MIGRATING.md`](docs/MIGRATING.md) |
| Release notes | [`docs/RELEASE_NOTES.md`](docs/RELEASE_NOTES.md) |

---

## ✉ Get in touch

Morpheus is built and run by **Marko Tiosavljevic**, and the three live stores are his proof that it holds up. He reads and answers every message himself.

**[marko@morpheus.direct](mailto:marko@morpheus.direct)** · [morpheus.direct](https://morpheus.direct)

Write if you are:

- **A merchant** who wants a store on Morpheus — set up, themed, migrated from Shopify, WooCommerce, Magento or BigCommerce, and run with an AI operator — under a per-store licence, with no share of your sales.
- **An agency or developer** who wants to build on it, ship an app or a theme, or bring a client's store across.
- **A partner or investor** who sees the same shift to agentic commerce and wants to talk about the road ahead.
- **Anyone** who found a bug, has a question, or wants a walkthrough of a live store.

Say what you sell, where you sell it today, and what you want to change. You will get a straight answer.

---

## 🤝 Contributing

Read [`CONTRIBUTING.md`](CONTRIBUTING.md) and the house rules in [`CLAUDE.md`](CLAUDE.md). The short version: it's an app unless it is genuinely foundational; add a migration; keep it disable-safe; update the docs in the same commit; and bump the version on anything that deploys.

## 📄 License

**[Business Source License 1.1](LICENSE)**. In plain words:

- You may read the code, run it for evaluation, development and testing, change it, and pass it on under the same terms — free.
- **Production use needs a commercial licence** from the licensor: running a store on it, or any other use for a business. One licence per store; no revenue share, no seat count. Write to [marko@morpheus.direct](mailto:marko@morpheus.direct).
- **Each version becomes open source on a schedule.** Four years after a version is published, it is relicensed to Apache 2.0 automatically.
- Versions up to v0.76.0 were published under Apache 2.0 and stay that way; the Business Source License applies from v0.76.1.

The BSL is a source-available licence, not an open-source one, by design: it keeps the code readable and the platform yours while funding the work. Third-party components keep their own licences.

<div align="center">

**[▶ dotbooks.store](https://dotbooks.store) · [supernatural-shop.com](https://supernatural-shop.com) · [montenegro-experience.me](https://montenegro-experience.me)**

*Morpheus OS — commerce you own, run by an AI you can trust, bought by agents.*

**[marko@morpheus.direct](mailto:marko@morpheus.direct)**

</div>
