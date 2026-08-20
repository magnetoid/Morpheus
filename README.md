<div align="center">

# Morpheus OS

### Commerce you own. Run by an AI you can actually trust with the keys.

*Describe your shop in one sentence and get a real, stocked storefront. Toggle a hundred-odd capabilities on and off like apps. Then hand the back office to an AI operator who knows your catalog, briefs you every morning, and proposes improvements to her own source code — every one of them reviewed by a panel of independent models, and then by you.*

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Live store](https://img.shields.io/badge/live-dotbooks.store-ff5722.svg)](https://dotbooks.store)
[![Self-host](https://img.shields.io/badge/self--host-no%20platform%20fees-16a34a.svg)](#-quick-start)
[![Apps](https://img.shields.io/badge/apps-100%2B%20toggleable-2563eb.svg)](#-everything-is-an-app)
[![AI operator](https://img.shields.io/badge/AI-built--in%20operator%20(Linda)-e11d48.svg)](#-meet-linda--the-ai-operator)
[![Agentic](https://img.shields.io/badge/agentic-MCP%20%2F%20ACP%20%2F%20UCP-7c3aed.svg)](#-agentic-commerce-be-transactable-by-ai)
[![Stack](https://img.shields.io/badge/django%206-postgres%20%C2%B7%20celery%20%C2%B7%20graphql-092e20.svg)](#-tech-stack)

**[▶ See it live](https://dotbooks.store)  ·  [🚀 Run your own](#-quick-start)  ·  [🧠 Architecture](#-architecture-a-small-kernel-a-deep-ecosystem)  ·  [🤖 Agentic surface](#-agentic-commerce-be-transactable-by-ai)  ·  [📚 Docs](#-documentation)**

</div>

---

## The problem with every other option

**Hosted SaaS rents you your own store.** You pay a percentage of every sale, then pay again for the apps that make it work, and the AI features arrive as a per-seat upsell that runs on somebody else's infrastructure, trained on somebody else's roadmap. The day the pricing changes, you have no move.

**Open-source alternatives hand you a codebase and wish you luck.** You own the code, which means you own the integration work, the agent surface nobody has built yet, and the governance layer that would make an LLM safe to point at your refund button.

**And both are about to have the same problem.** A growing share of shopping now starts inside an assistant. If a model can't read your catalog, quote your real shipping, and complete a cart, you don't lose a ranking — you lose the conversation entirely, to whoever the model *can* transact with.

Morpheus is the third option: **a full commerce engine you run yourself, built from the ground up to be operated by an AI and transacted with by one.**

---

## What makes it different

Three convictions, and each one shows up as code rather than a roadmap item.

### 1. The AI is staff, not a subscription

One generalist operator — **Linda** — runs on your servers. She reads your catalog, executes real back-office work through a typed tool registry, writes you a morning brief, and opens pull requests against her own platform.

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
- [Meet Linda — the AI operator](#-meet-linda--the-ai-operator)
- [Agentic commerce: be transactable by AI](#-agentic-commerce-be-transactable-by-ai)
- [Found by search, and by answer engines](#-found-by-search-and-by-answer-engines)
- [Architecture: a small kernel, a deep ecosystem](#-architecture-a-small-kernel-a-deep-ecosystem)
- [Everything is an app](#-everything-is-an-app)
- [The self-improvement loop](#-the-self-improvement-loop)
- [Safety, security & compliance](#-safety-security--compliance)
- [What this is not (yet)](#-what-this-is-not-yet)
- [Tech stack](#-tech-stack)
- [Quick start](#-quick-start)
- [Project structure](#-project-structure)
- [Development workflow](#-development-workflow)
- [Deployment](#-deployment)
- [Documentation](#-documentation)
- [License](#-license)

---

## ✨ Why Morpheus

| | Morpheus | Hosted SaaS (Shopify/BigCommerce) | Other open source (Woo/Medusa/Saleor) |
|---|---|---|---|
| **AI operator** | Built in, governed, on *your* infra | Add-on / per-seat copilot | Bring your own |
| **Agent-transactable** | MCP + ACP + UCP, native | Emerging, platform-mediated | Rare |
| **Feature model** | 100+ apps, disable-safe by construction | Apps (billed, sandboxed) | Extensions / modules |
| **Own your data & code** | Yes — self-hosted, Apache-2.0 | No | Yes |
| **Platform fees** | None | % of revenue + app fees | None |
| **Self-improving** | Code changes reviewed by an LLM panel, then by you | — | — |
| **EU AI Act ready** | Art. 50 disclosure + evidence export | Varies | Bring your own |

**Who this is for**

- Merchants who want capability at the level of a hosted platform without paying a share of every order to get it.
- Teams who want an AI staff member with real guardrails rather than a chat window bolted to an admin panel.
- Builders who can see where commerce is heading and would rather own the surface an agent talks to than rent it.

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

The rest of the governance, all enforced in `core/` and read from one place:

| Control | What it does |
|---|---|
| **Scopes** | Every tool declares what it needs; a caller only sees tools it may call |
| **Human approval** | High-risk writes create a server-side, single-use, argument-bound record — and fail closed if the approver is down |
| **Staged writes** | An agent can record a proposal for review instead of executing |
| **Merchant guardrails** | Kill switch, daily run and spend caps, per-action price and refund ceilings |
| **Budgets & deadlines** | One execution kernel owns them, so no tool can opt out |
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

  Discovery is anonymous. **Executing** anything requires a Bearer token, per-token scopes, rate limits, a per-token approval grant for protected writes, and an audit row.

- **ACP checkout** (`/acp/…`) — a conformant Agentic Commerce Protocol session: multi-item carts, live tax and shipping quotes, refusal to charge when the quote has drifted, idempotent completion under a row lock. It reuses the canonical order and money path, so there is exactly **one** implementation of totals — no chance of MCP and ACP disagreeing about what a cart costs.

- **UCP manifest** (`/.well-known/ucp.json`) — capabilities computed **live** from what is actually registered and enabled. It cannot advertise a feature you turned off.

- **Trusted agents** — when Cloudflare verifies a signed agent request (Visa Trusted Agent Protocol, Mastercard Verifiable Intent), Morpheus honours the stamped headers — but **only from a verified proxy origin**, and it fails closed by default. An unverified caller claiming to be a trusted agent is simply a stranger.

Deep dive: [`docs/MCP_SERVER.md`](docs/MCP_SERVER.md) · [`docs/AGENT_PROTOCOLS.md`](docs/AGENT_PROTOCOLS.md) · [`docs/MORPHEUS_API.md`](docs/MORPHEUS_API.md).

---

## 🔎 Found by search, and by answer engines

Most platforms treat SEO as a settings page. Morpheus treats the `<head>` as a **document the platform owns**, which is the only way it can be correct on *any* theme.

A theme calls one tag. Core seeds a document, fires a filter, and the SEO app fills in the title, description, canonical, robots directive, Open Graph, hreflang, and a single JSON-LD graph. Every entry is *keyed*, so a second writer replaces the first instead of shipping the page with two `og:type` tags and two `WebSite` nodes.

What that buys you, concretely:

- **Structured data that is a claim, not a decoration.** A property that cannot be sourced from the app that owns it is **omitted, never defaulted** — because inventing a shipping policy is a Merchant Center violation and a promise checkout will break. Shipping comes from your shipping rates, returns from your returns policy, availability from real inventory. A product sold in several editions is published as a `ProductGroup` with per-variant price and stock.
- **An index-rules engine.** One rule per query parameter, deciding whether `?sort=`, `?genre=` or a campaign tag makes a real page, a page to keep out of search, a landing page for values you choose, or an address crawlers should never fetch. Paste any URL into the dashboard and see exactly what your store publishes for it, and which rule decided.
- **Pagination that tells the truth.** Page 2 is a page and says so; `?page=1` redirects to the clean address; a page number past the end is a 404 rather than a silent duplicate of page one.
- **AI-crawler control** — a per-bot matrix separating training crawlers from retrieval crawlers, so you can stay citable in AI answers without feeding a training run.

---

## 🏗️ Architecture: a small kernel, a deep ecosystem

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
        catalog        orders      payments     agent_mcp    …103 more apps
         (an app)     (an app)     (an app)      (an app)   in plugins/installed/
```

**What lives in `core/`:** only what is genuinely foundational — auth, the event bus, settings, request lifecycle, the i18n kernel, observability, the agent runtime, the safety boundary (`core/safety.py`, the single source of truth for what AI may touch), and the self-improvement loop. Nothing else.

A CI ratchet (`scripts/check_core_boundary.py`) enforces that `core/` imports **zero** apps. Not "few". Zero — the allowlist is empty and a single new leak fails the build. A sibling ratchet stops apps importing each other except through declared dependencies and hooks, and its baseline can only ever shrink.

**Core fires, apps answer.** When the dashboard needs to know whether you may refund an order, it doesn't import the permissions app — it fires a capability check and whoever owns permissions answers. Same inversion for pricing rules, structured data, robots directives and the storefront head. That one pattern is why an app can be disabled without leaving a hole.

**Three SDK doors** curate the common imports:

| Door | For | Exposes |
|---|---|---|
| `morpheus.app` | app authors | `Plugin`, `StorefrontBlock`, `DashboardPage`, `SettingsPanel`, `.views/.models/.forms` |
| `morpheus.core` | cross-cutting | `events`, `hooks`, `tool`, `ToolResult`, `record_ai_decision`, `Money`, … |
| `morpheus.theme` | theme authors | the storefront slot contract |

More: [`ARCHITECTURE.md`](ARCHITECTURE.md) · [`docs/PLUGIN_DEVELOPMENT.md`](docs/PLUGIN_DEVELOPMENT.md) · [`CHARTER.md`](CHARTER.md).

---

## 🧩 Everything is an app

Every shipped capability is a toggleable app. The count moves with most releases, so the source of truth is `MORPHEUS_DEFAULT_APPS` in `morph/settings.py` rather than a number in this file — at the time of writing it is a little over a hundred. A sampling by domain:

> **Apps and plugins are the same thing.** "App" is the word the product uses — in the dashboard, in these docs, and at every seam you touch as an author (`app.py`, `morpheus.app`, `app_registry`). Two things still read "plugin" on purpose: the directory `plugins/installed/` and the base class `MorpheusPlugin`, because renaming them would rewrite roughly two thousand import paths for no user-visible gain. Upgrading an out-of-tree app: [`docs/MIGRATING.md`](docs/MIGRATING.md).

- **Core commerce** — `catalog` · `orders` · `inventory` · `payments` · `shipping` · `tax` · `checkout_experience` · `draft_orders` · `customers` · `one_click` · `smart_shipping` · `advanced_payments`
- **Merchandising & pricing** — `promotions` · `gift_cards` · `loyalty_points` · `subscriptions` · `drops` · `markets` · `metafields`
- **AI & agents** — `agent_core` · `agent_mcp` · `agentic_checkout` · `ai_assistant` · `ai_content` · `ai_stylist` · `morpheus_brain` · `discovery_quiz` · `personalisation` · `lumina`
- **Storefront & immersive** — `storefront` · `cms` · `richtext` · `media` · `media_3d` · `bookstore_3d` · `immersive_pdp` · `flipbook` · `lookbook` · `product_stories` · `product_videos` · `webstories` · `live_commerce` · `pwa`
- **Growth & retention** — `marketing` · `seo` · `newsletter` · `referrals` · `affiliates` · `reviews` · `ugc_reviews` · `trust_signals` · `cart_abandonment` · `post_purchase` · `post_checkout_upsell` · `save_for_later` · `wishlist` · `experiments`
- **Channels & marketplaces** — `google_shopping` · `meta_commerce` · `tiktok_commerce` · `pinterest_commerce` · `microsoft_commerce` · `snapchat_commerce` · `reddit_ads` · `amazon_ads` · `channels` · `marketplace`
- **B2B & internationalisation** — `b2b` · `markets` · `localization`
- **Ops, security & compliance** — `admin_dashboard` · `rbac` · `staff_mfa` · `staff_sso` · `gdpr` · `consent` · `fraud_rules` · `observability` · `backups` · `webhooks_ui` · `notifications_center` · `analytics` · `workflows` · `cloudflare`
- **Verticals** — `book_product` · `bookvault` · `audiobooks` · `booking_marketplace` · `digital_products` · `eco_impact`

> **Before adding an app:** audit for overlap and justify the boundary. *One concept, one owner.* A previous release shipped a second, incompatible returns table that was invisible to the dashboard, to return numbers, and to the refund service. The rule exists because ignoring it cost a release.

---

## ♻️ The self-improvement loop

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
- **Staff MFA & SSO** — second factor and SSO ship as apps, with a guard ensuring no new sign-in path can quietly bypass MFA.
- **RBAC** — role capabilities for staff, per-token scopes for agents. The seam fails *open* on absence by design: an authorisation layer that locked every merchant out of their own dashboard when its answerer was missing would be a worse bug than the one it prevents.
- **GDPR & consent** — data-subject flows and consent-gated analytics.
- **EU AI Act** — Article 50 disclosure for synthetic content, plus a dated evidence export of the decision and approval trail.
- **Supply chain** — hash-pinned `requirements.lock.txt`, `pip-audit` and `bandit` in CI, Dependabot on.
- **Signed updates** — release manifests are Ed25519-signed and verification **fails closed**; an update whose bytes do not match its signed checksum is refused before it is ever unpacked.

See [`SECURITY.md`](SECURITY.md) · [`docs/COMPLIANCE.md`](docs/COMPLIANCE.md).

---

## 🧾 What this is not (yet)

A README that only lists wins is a sales page. Here is the honest edge of the thing, because you will find it anyway on day two:

- **This is a 0.x project.** It runs a real store in production and ships most weeks, but the version number means what it says.
- **Some surfaces are deeper than others.** Core commerce, the agent layer and SEO have had the most attention. Search Console integration, the site crawler and bulk AI content tooling are specified and not yet built.
- **A few screens are still ahead of their data.** Keyword tracking, for instance, has a page but nothing yet writes positions into it — it is waiting on the Search Console work.
- **It is opinionated to the point of being bossy.** One AI worker, not many. Everything is an app. Core imports nothing. If you disagree with those, you will be fighting the grain of the codebase rather than riding it.

The full, dated list of what shipped and when is in [`docs/RELEASE_NOTES.md`](docs/RELEASE_NOTES.md), and the breaking changes are in [`docs/MIGRATING.md`](docs/MIGRATING.md). Both are maintained because a deploy without a changelog entry fails CI.

---

## 🛠 Tech stack

- **Django 6** (Python 3.12) · **PostgreSQL** · **Redis** · **Celery** (+ beat)
- **Strawberry GraphQL** (the stable public API) + **DRF** for REST
- **djmoney** for multi-currency money · **allauth** for auth and SSO
- **MCP / ACP / UCP** agent protocols
- Container-first (`Dockerfile`, `docker-compose.yml`); the reference deployment runs behind **Cloudflare → Plesk → Coolify (Traefik)**

---

## 🚀 Quick start

> **Access:** the repository is private while Morpheus is in active build-out —
> the clone below works once you've been added as a collaborator. Not on the
> list yet? Ask [@magnetoid](https://github.com/magnetoid) for an invite.

### Option A — Docker (the full stack: Postgres, Redis, worker, beat)

```bash
git clone https://github.com/magnetoid/morpheus.git
cd morpheus
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

---

## 📁 Project structure

```
morph/
├── core/                      # the kernel: auth, hooks, agent runtime, safety, self-improvement
│   ├── agents/                # agent runtime, tool registry, guardrails, approvals
│   ├── assistant/             # Linda's conversational runtime
│   ├── hooks.py               # the fire/filter event bus (all cross-app coupling goes here)
│   └── safety.py              # single source of truth for what AI may touch
├── morph/                     # Django project: settings, root urls, MORPHEUS_DEFAULT_APPS
├── morpheus/                  # the three SDK doors: {app, core, theme}
├── plugins/installed/<name>/  # every feature — app.py, apps.py, models, migrations, templates
├── themes/                    # storefront themes (contribution-driven; e.g. dot_books)
├── api/                       # GraphQL view + hardening
├── scripts/                   # CI ratchets (core boundary, app boundary, API stability, release)
├── docs/                      # architecture, app development, MCP, API, compliance, runbooks
└── docker-compose.yml         # the full local stack
```

---

## 🧭 Development workflow

Morpheus is built for AI-assisted development with hard guardrails. The house rules live in [`CLAUDE.md`](CLAUDE.md) and [`AGENTS.md`](AGENTS.md), and they are mostly a record of things that went wrong once:

- **One concept, one owner.** Extend another app with a foreign key and hooks, never a parallel table.
- **Add a migration before merge.** A model without one fails the system check on every production boot, and CI applies every migration against real Postgres.
- **Ship code and docs together.** A change to architecture, a convention, or a public contract updates the matching Markdown in the same commit — not "later".
- **Every deploy bumps the version.** `python manage.py release --minor "Headline" -m "bullet"` updates the version and prepends a dated release-notes entry atomically. `release --check` is a blocking gate.
- **Verify for real.** A green lint and type check is necessary, not sufficient. Smoke the actual behaviour, then smoke it again on the live URL.

There is a fifth rule that is really the other four combined: **a passing test proves only what it asserts.** New guards here are mutation-tested — the guard is deliberately broken to confirm a test actually fails. More than one test in this repo has been caught passing for entirely the wrong reason.

---

## 🗂️ Project memory: torsor-helper

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

Guides: [`docs/deploy-coolify.md`](docs/deploy-coolify.md) · [`docs/deploy-plesk-nginx.md`](docs/deploy-plesk-nginx.md) · recovery procedures in [`docs/OPERATIONS_RUNBOOK.md`](docs/OPERATIONS_RUNBOOK.md).

---

## 📚 Documentation

| Topic | Doc |
|---|---|
| System architecture & request lifecycle | [`ARCHITECTURE.md`](ARCHITECTURE.md) · [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) |
| Product charter & principles | [`CHARTER.md`](CHARTER.md) · [`AI_VISION.md`](AI_VISION.md) |
| Building an app | [`docs/PLUGIN_DEVELOPMENT.md`](docs/PLUGIN_DEVELOPMENT.md) |
| Building a theme | [`docs/THEME_DEVELOPMENT.md`](docs/THEME_DEVELOPMENT.md) · [`docs/THEME_EXTENSIONS.md`](docs/THEME_EXTENSIONS.md) |
| Public API (GraphQL / REST) | [`docs/MORPHEUS_API.md`](docs/MORPHEUS_API.md) · [`docs/API_STABILITY.md`](docs/API_STABILITY.md) |
| Agent protocols (MCP / ACP / UCP) | [`docs/MCP_SERVER.md`](docs/MCP_SERVER.md) · [`docs/AGENT_PROTOCOLS.md`](docs/AGENT_PROTOCOLS.md) |
| AI skills | [`docs/SKILLS.md`](docs/SKILLS.md) |
| Compliance (GDPR / EU AI Act) | [`docs/COMPLIANCE.md`](docs/COMPLIANCE.md) |
| Headless usage | [`docs/HEADLESS.md`](docs/HEADLESS.md) |
| Webhooks | [`docs/WEBHOOK_RECIPES.md`](docs/WEBHOOK_RECIPES.md) |
| Operations & incident recovery | [`docs/OPERATIONS_RUNBOOK.md`](docs/OPERATIONS_RUNBOOK.md) · [`docs/PERFORMANCE.md`](docs/PERFORMANCE.md) |
| House rules for AI-assisted work | [`CLAUDE.md`](CLAUDE.md) · [`AGENTS.md`](AGENTS.md) · [`RULES.md`](RULES.md) |
| Updating a deployment | [`docs/UPDATING.md`](docs/UPDATING.md) |
| Upgrading across a breaking change | [`docs/MIGRATING.md`](docs/MIGRATING.md) |
| Release notes | [`docs/RELEASE_NOTES.md`](docs/RELEASE_NOTES.md) |

---

## 🤝 Contributing

Read [`CONTRIBUTING.md`](CONTRIBUTING.md) and the house rules in [`CLAUDE.md`](CLAUDE.md). The short version: it's an app unless it is genuinely foundational; add a migration; keep it disable-safe; update the docs in the same commit; and bump the version on anything that deploys.

## 📄 License

[Apache License 2.0](LICENSE) — self-host it, modify it, sell with it, own it. No platform fees, no seat count, no revenue share.

<div align="center">

**[▶ See it running at dotbooks.store](https://dotbooks.store)**

*Morpheus OS — commerce you own, run by an AI you can trust.*

</div>
