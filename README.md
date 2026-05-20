<div align="center">

# Morpheus

### A commerce platform built natively for AI agents.

**Open source · Plugin-first · Event-sourced · Production-grade · Agentic-commerce ready**

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![Live demo](https://img.shields.io/badge/live-dotbooks.store-ff5722.svg)](https://dotbooks.store)
[![Plugins](https://img.shields.io/badge/plugins-49%20active-blue.svg)](#whats-inside)
[![MCP](https://img.shields.io/badge/MCP-ready-7c3aed.svg)](#agentic-commerce-surfaces)
[![One-prompt bootstrap](https://img.shields.io/badge/bootstrap-1%20prompt%20%E2%86%92%20live%20store-22c55e.svg)](#one-prompt-store-bootstrap)
[![Stack](https://img.shields.io/badge/django%206-postgres-2563eb.svg)](#tech-stack)

[Quick start](#quick-start) · [The mental model](#the-mental-model) · [What's inside](#whats-inside) · [The agent layer](#the-agent-layer) · [Agentic commerce surfaces](#agentic-commerce-surfaces) · [Showcase](#showcase) · [Docs](#documentation)

</div>

---

## Why Morpheus exists

Every commerce platform built before 2024 — Shopify, WooCommerce, Magento, Spree, Saleor, Medusa — treats AI as a *third-party API consumer*. You bolt OpenAI onto a checkbox in settings, hope the prompt is good, and pay an integration tax forever.

**Morpheus is the only self-hostable, agent-native commerce stack.** Saleor, Medusa, and Vendure are excellent platforms — but none ship the multi-protocol agent gateway that Shopify Sidekick, Adobe Commerce, and BigCommerce are racing toward. Morpheus already does.

| Capability | Morpheus | Saleor | Medusa | Vendure |
|---|:---:|:---:|:---:|:---:|
| MCP server cluster (storefront / cart / checkout / admin) | ✅ | — | — | — |
| Universal Commerce Protocol (`/.well-known/ucp.json`) | ✅ | — | — | — |
| Visa TAP + Mastercard VI acceptance (`/.well-known/agent.json`) | ✅ | — | — | — |
| Always-on hard-coded merchant assistant (Linda) | ✅ | — | — | — |
| Hybrid retrieval (BM25 + dense + RRF) on storefront search | ✅ | — | — | — |
| EU AI Act decision-provenance audit trail | ✅ | — | — | — |
| Plugin-isolated runtime + first-party plugin catalog | ✅ | ✱ | ✱ | ✱ |
| GraphQL + signed webhook fanout | ✅ | ✅ | ✅ | ✅ |

(✱ = extension framework exists, no plugin-isolation guarantees comparable to Morpheus's `safe_db` + crash-isolation contract.)

**Morpheus inverts the integration tax.** AI agents are the *primary audience*. Every model, hook, dashboard, and state transition is designed to be machine-actionable first and human-pretty second. The Assistant is not a chatbot tab — it's a hard-coded operator in `core/` that survives plugin failure, has system-level scopes, **20+ tools spanning read and gated writes**, and can delegate to specialised agents that other plugins contribute. External AI clients reach the platform over a real **Model Context Protocol** server at `/mcp/v1/`, with brand voice config that propagates to every generation in the system.

What you get:

| Pillar | What it means in practice |
|---|---|
| **Hard-coded Assistant in core** | A single Morpheus Assistant lives in [`core/assistant/`](core/assistant/) — never a plugin. **20 first-class tools** spanning filesystem, DB introspection, ecommerce reads (orders / products / customers / analytics / content / settings / media / metafields) and gated writes (orders.cancel, products.update_price, metafields.set, …). JSONL fallback persistence so the chat works even when the DB is unreachable. |
| **Kernel agent layer** | [`core/agents/`](core/agents/) is a peer of `core/hooks` and `plugins/`. Real LLM tool-use loop, provider abstraction (OpenAI / Anthropic / Gemini / OpenRouter / Ollama / Mock), versioned prompts, capability scopes, lossless trace, **Skills** (reusable tool bundles), background scheduling, **brand-voice-aware system prompts**. |
| **Agentic-commerce ready** | First-class **MCP server** at `/mcp/v1/` exposes a curated read surface (products, orders, analytics, …) to external AI clients via JSON-RPC 2.0. Bearer-token auth, ChatGPT-style `manifest.json`, three resource URIs. |
| **Plugin-native everything** | **43 plugins** ship enabled. Each contributes any of: storefront blocks, dashboard pages, settings panels, hooks, agents, agent tools, skills, URLs, GraphQL extensions, beat tasks. **Plugin crashes are isolated** — a broken `ready()` is logged and that plugin is excluded; siblings keep loading. |
| **Event-sourced + outbox** | Every state change emits a hook *and* writes to a transactional outbox shipped to NATS JetStream. Replayable, auditable, fanout-friendly. HMAC-SHA256 on every outbound webhook. |
| **Schema-less custom data** | A first-class [`metafields`](plugins/installed/metafields/) plugin: `(content_type, object_id, namespace, key, value)` triples on **any** Django model out of the box. The Shopify escape valve, but generic. |
| **Central media library** | A dedicated [`media`](plugins/installed/media/) plugin: one `MediaAsset` model, sharded uploads, kind tabs, embeddable picker — used everywhere a file ID is needed. |

Live deployment: **https://dotbooks.store** · 49 plugins · 6 built-in agents · 1 hard-coded Assistant · 1 MCP server · ~20-second one-prompt store bootstrap.

### One-prompt store bootstrap

A merchant types one sentence — *"A modern Japanese tea shop selling single-estate matcha, sencha, and hand-thrown ceramics"* — and the [`store_bootstrap`](plugins/installed/store_bootstrap/) plugin uses the active LLM gateway to generate brand voice, 4-6 categories, and 10-12 starter products with copy, prices, and SKUs. The whole thing finishes in ~20 seconds. No other open-source commerce platform ships this.

```
/dashboard/apps/store_bootstrap/start/
  →  prompt → LLM → JSON plan → Category.get_or_create × N → Product.create × M
  →  brand voice written to ai_content config (propagates to every future generation)
  →  ready storefront at https://your.shop/products/
```

Idempotent by SHA-256 of the prompt — re-running the same sentence re-uses the existing categories rather than duplicating them. JSON-repair pass handles trailing commas, unescaped newlines, and code-fence wrappers that LLMs slip into "strict JSON" output.

---

## Quick start

### Deploy to Coolify (the recommended path)

```text
+ New Resource → Docker Compose
  Repo:         https://github.com/magnetoid/morpheus
  Compose file: docker-compose.yml          ← default; no override needed
  Env vars:     paste from .env.coolify.example
  Domain:       bind your.domain.com to the `web` service
```

The default `docker-compose.yml` ships **web + worker + beat + postgres + redis + pgbouncer** wired through Coolify magic vars (`SERVICE_FQDN_WEB`, `SERVICE_PASSWORD_POSTGRES`, `SERVICE_PASSWORD_REDIS`). The web container's entrypoint waits for the DB, runs `migrate` + `collectstatic`, then execs gunicorn.

Full guide: [`docs/deploy-coolify.md`](docs/deploy-coolify.md) · Behind Plesk Nginx: [`docs/deploy-plesk-nginx.md`](docs/deploy-plesk-nginx.md)

### Plain `docker compose`

```bash
git clone https://github.com/magnetoid/morpheus.git
cd morpheus
cp .env.example .env       # set SECRET_KEY, DATABASE_URL, REDIS_URL …
docker compose up -d
```

### Local dev (no Docker)

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

export DATABASE_URL=postgresql://user:pass@localhost/morpheus
export SECRET_KEY=dev-secret
export REDIS_URL=redis://localhost:6379/0

python manage.py migrate
python manage.py createsuperuser
python manage.py morph_seed_demo          # 25 demo books + 1 paid order
python manage.py runserver

celery -A morph worker -l info             # in another shell
celery -A morph beat -l info               # for observability rollups + agent scheduler
```

For the full stack with observability: `docker compose -f docker-compose.dev.yml up -d`

---

## The mental model

Three layers, two registries. Internalise this and the rest of the codebase reads itself.

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                                LAYER 1 — CORE                                │
│  Tiny, almost everything else can be ripped out and the engine still boots.  │
│                                                                              │
│  core/                hooks · models · tasks · settings · request_id · logs  │
│  core/assistant/      ★ HARD-CODED MORPHEUS ASSISTANT (always reachable)     │
│  core/agents/         ★ Agent kernel (MorpheusAgent · Tool · Skill · LLM)    │
│  core/audit/          ★ Tamper-evident security log                          │
│  core/i18n/           ★ Translation kernel (generic-FK Translation rows)     │
│  core/embeddings.py   ★ Embedding provider abstraction                       │
│  core/utils/          ★ safe_db decorator · sliding-window rate limiter      │
│  core/management/     ★ morph_backup (pg_dump + media tar)                   │
└──────────────────────────────────────────────────────────────────────────────┘
                                     │
                          ┌──────────┼──────────┐
                          ▼          ▼          ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                              LAYER 2 — PLUGINS                                │
│           49 enabled by default. Each is a self-contained Python package.    │
│                                                                              │
│  COMMERCE         AI / AGENTS        FOUNDATIONS       INFRA / OPS            │
│  catalog          agent_core         media ★           cloudflare             │
│  orders           agent_mcp ★        metafields ★      observability          │
│  customers        ai_assistant       importers         environments           │
│  payments         ai_content         seo               webhooks_ui            │
│  inventory        functions          rbac              backups                │
│  cms              store_bootstrap ★                    demo_data              │
│  tax                                                   tracking ★             │
│  shipping         GROWTH             B2B               admin_dashboard        │
│  promotions       crm                b2b               advanced_ecommerce     │
│  draft_orders     affiliates         subscriptions     analytics              │
│  storefront       marketplace        digital_products  product_gallery        │
│  gift_cards       marketing                            product_videos         │
│  reviews          loyalty_points     notifications_                           │
│                   wishlist           center                                   │
│                   cart_abandonment                                            │
└──────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                              LAYER 3 — THEMES                                 │
│       Plugins ship features. Themes ship presentation. They never mix.       │
│                                                                              │
│  themes/library/dot_books/   ← active by default; modern editorial            │
│                                                                              │
│  Plugins contribute via {% storefront_blocks "slot" %} into theme slots.     │
│  The theme owns layout + CSS + which slots exist — that's the boundary.      │
└──────────────────────────────────────────────────────────────────────────────┘

The two registries that wire it all together:

  PluginRegistry        — discovers, topologically sorts, activates.
                          Crashes in plugin.ready() are caught + isolated.
                          Collects each plugin's contributions:
                          • storefront blocks  • dashboard pages  • settings panels
                          • agents · agent tools · skills · URLs · GraphQL extensions

  AgentRegistry         — knows every Tool and every Agent the platform exposes.
                          Skills resolve into Tool bundles at agent invocation time.
```

★ = recently added.

### Three non-obvious rules

1. **The Assistant is not a plugin.** Lives in `core/`. Survives plugin failure. Mounted at `/dashboard/assistant/` *before* the plugin URL prefix so it remains reachable even if every plugin import explodes. JSONL fallback persistence so the chat keeps working when the DB is down.
2. **Operational pages live in the main sidebar; persistent configuration lives in Settings.** Promotions, draft orders, demo-data generators — those are *operational pages* and surface under main-menu sections (Marketing / Sales / Catalog). Settings panels are reserved for things you set once: API keys, provider choice, on/off toggles.
3. **Every write goes through hooks.** `order.placed`, `product.updated`, `agent.intent.completed`, `cart.checkout.totals` — handlers can transform or veto. The agent runtime calls `hook_registry.filter(AgentEvents.TOOL_CALLING, …)` before every tool call so plugins can intercept.

---

## What's inside

### Engine modules (`core/` — the small fixed surface)

| Module | Role |
|---|---|
| [`core/`](core/) | hooks, models, Celery, observability bootstrap, request_id, JSON logging, Sentry, channels, exchange rates, money helpers |
| [`core/assistant/`](core/assistant/) | **Hard-coded Morpheus Assistant** — runtime, providers, **20 system + ecommerce tools**, JSONL-fallback persistence |
| [`core/agents/`](core/agents/) | Agent kernel — `MorpheusAgent`, `Tool`, **`Skill`**, `AgentRuntime`, `LLMProvider`, prompts registry, scopes, trace, policies |
| [`core/audit/`](core/audit/) | **Tamper-evident audit log** — `core.audit.record(event_type, actor, target, metadata)` |
| [`core/i18n/`](core/i18n/) | **Translation kernel** — generic-FK `Translation` rows, `{{ obj\|trans:"field" }}`, agent tools |
| [`core/embeddings.py`](core/embeddings.py) | **Embedding provider abstraction** — deterministic-hash fallback so tests work without API keys |
| [`core/money.py`](core/money.py) | Currency-safe arithmetic — every op returns a `CENTS`-quantized `Money`; `CurrencyMismatch` raised loudly |
| [`core/utils/`](core/utils/) | `safe_db` decorator · sliding-window `rate_limit` |
| [`core/management/commands/`](core/management/commands/) | `morph_backup` — pg_dump + media tar with retention |
| [`api/`](api/) | GraphQL view (depth/alias guarded, masked errors), REST viewsets, agent-only endpoint, exception handler, idempotency middleware, rate limiter |
| [`plugins/`](plugins/) | plugin base class + registry with topological-sort activation; `morph_create_plugin` scaffolder |
| [`themes/`](themes/) | theme base + registry + ThemeLoader; `morph_create_theme` scaffolder |
| [`morph/`](morph/) | Django settings, ASGI/WSGI, Celery |

### First-party plugins (49 active)

#### Commerce

| Plugin | What it does |
|---|---|
| [`catalog`](plugins/installed/catalog/) | Products, variants, categories, collections, attributes, vendors — `agent_metadata` on every Product |
| [`orders`](plugins/installed/orders/) | Cart → Order FSM, fulfillments, refunds, immutable `OrderEvent` log, **authoritative `cart_totals` GraphQL query** |
| [`customers`](plugins/installed/customers/) | Custom user + addresses + CDP fields (`lifetime_value`, `purchase_count`, `last_order_at`) |
| [`payments`](plugins/installed/payments/) | `PaymentGateway` ABC + `GatewayRegistry`. Stripe + Manual adapters; idempotent intents |
| [`inventory`](plugins/installed/inventory/) | Stock movements, low/back-in-stock hooks, `allocator.plan_allocation()` for multi-warehouse splits |
| [`promotions`](plugins/installed/promotions/) | Rule-based engine — JSON predicates × actions (% off, fixed off, free shipping, gift, BOGO, tiered) |
| [`draft_orders`](plugins/installed/draft_orders/) | Quote / invoice flow — build a priced cart, share with customer, convert on payment |
| [`tax`](plugins/installed/tax/) | Regions + categorised rates (US sales tax / EU VAT / OSS); cart-total hook |
| [`shipping`](plugins/installed/shipping/) | Zones + rates (flat / weight / order-total tier / free-over / Shippo / EasyPost slots) — **real weight-unit conversion** |
| [`gift_cards`](plugins/installed/gift_cards/) | Issue / redeem / balance, append-only ledger, checkout-time discount |
| [`subscriptions`](plugins/installed/subscriptions/) | Plan + Subscription + invoice; Stripe Billing adapter slot |
| [`digital_products`](plugins/installed/digital_products/) | Token-gated downloads with expiry + count limits |
| [`reviews`](plugins/installed/reviews/) | Star ratings + verified-purchase signal |

#### AI / Agents

| Plugin | What it does |
|---|---|
| [`agent_core`](plugins/installed/agent_core/) | **Persistence + GraphQL + dashboard for the agent kernel.** Built-in agents (Concierge, Merchant Ops, Pricing, Content Writer). Background agents lifecycle + observability dashboard |
| [`agent_mcp`](plugins/installed/agent_mcp/) ★ | **MCP server** — JSON-RPC 2.0 endpoint at `/mcp/v1/` so external AI clients can transact through Morpheus without per-vendor integrations |
| [`ai_assistant`](plugins/installed/ai_assistant/) | AI provider config (OpenAI / Anthropic / Gemini / OpenRouter / **Grok (xAI)** / Ollama), embeddings, semantic search, recommendations, dynamic pricing. Per-provider key + model + live model picker from `/v1/models` |
| [`ai_content`](plugins/installed/ai_content/) ★ | **Brand voice config** — single source of truth that propagates to every AI generation in the platform via `services.get_brand_voice()`. Tone, audience, guidelines edited once propagate to product copy, email rewrites, SEO drafts |
| [`store_bootstrap`](plugins/installed/store_bootstrap/) ★ | **One-prompt store seed** — merchant describes a concept in one sentence, plugin generates brand voice + categories + 10-12 starter products in ~20s. Idempotent on SHA-256 of prompt. The AI-first onboarding moment |
| [`functions`](plugins/installed/functions/) | Sandboxed merchant-defined logic for cart totals, pricing, shipping, validation |

#### Foundations

| Plugin | What it does |
|---|---|
| [`media`](plugins/installed/media/) ★ | **Central asset library** — single `MediaAsset` model, sharded uploads, kind tabs, embeddable picker, JSON upload API. Replaces per-model `ImageField` proliferation |
| [`metafields`](plugins/installed/metafields/) ★ | **Schema-less `(namespace, key, value)` triples on any record** via Django `GenericForeignKey`. Inline editor partial drops into any edit form sidebar |
| [`importers`](plugins/installed/importers/) | Idempotent migrators: **one-click Shopify CSV / Admin API import**, WooCommerce, fixture loader |
| [`seo`](plugins/installed/seo/) ★ | **Full 2026 SEO + AEO stack.** Per-object meta, JSON-LD (Product / ProductGroup w/ hasVariant / Offer with MerchantReturnPolicy + shippingDetails + gtin13 + brand + sameAs / BreadcrumbList / SpeakableSpecification / CollectionPage / FAQPage / QAPage / Article), `sitemap.xml` + `sitemap-images.xml` + `sitemap-news.xml` + `sitemap-index.xml`, `robots.txt` with **15-bot AI crawler matrix** (per-bot allow/disallow toggles in the dashboard for GPTBot / ClaudeBot / PerplexityBot / Google-Extended / Bytespider / Applebot-Extended / Meta-ExternalAgent / CCBot…), `/llms.txt` + `/llms-full.txt` with per-product `/md/` links, **per-product markdown export** at `/md/products/<slug>` so LLM crawlers ingest copy without HTML, **IndexNow** auto-push on product save (Bing/Yandex/Naver/Seznam/Yep), `/opensearch.xml` + `/manifest.json` (PWA), redirects, **Core Web Vitals RUM** via `/web-vitals/` beacon → dashboard p75 panel, **on-the-fly WebP/AVIF image variants** at `/img/<fmt>/<width>/<path>` + `{% seo_responsive_image %}` template tag with priority + view-transition-name + gallery-swap support |
| [`rbac`](plugins/installed/rbac/) | Named roles + capabilities — 6 system role templates, `has_capability(user, cap, channel=None)`, audit-logged grants |

#### Storefront / Admin

| Plugin | What it does |
|---|---|
| [`storefront`](plugins/installed/storefront/) | Public storefront views, customer account v2 (orders, addresses, returns, profile), gift-card redemption |
| [`admin_dashboard`](plugins/installed/admin_dashboard/) | **Shopify-style merchant admin** — sticky save bar, status tabs, sortable columns, real pagination, per-row action menus, two-column edit forms, command palette, date-range picker, real analytics page (KPIs + line chart + breakdowns), staff account page |
| [`cms`](plugins/installed/cms/) | Pages (state machine), Blocks, Menus, Forms (form submissions bridge into CRM as Lead+Interaction) |
| [`advanced_ecommerce`](plugins/installed/advanced_ecommerce/) | Recently viewed, free-shipping progress, low-stock badge, bulk price edit |

#### Growth

| Plugin | What it does |
|---|---|
| [`marketing`](plugins/installed/marketing/) | Coupons, email campaigns, redirects |
| [`crm`](plugins/installed/crm/) | Leads, accounts, deals, interactions timeline, follow-up tasks, IMAP/SMTP inbox |
| [`affiliates`](plugins/installed/affiliates/) | Programs, links, attribution, payouts |
| [`marketplace`](plugins/installed/marketplace/) | Vendor onboarding, per-vendor order splitting, payouts |
| [`loyalty_points`](plugins/installed/loyalty_points/) | Points + tiers + redemption |
| [`cart_abandonment`](plugins/installed/cart_abandonment/) | Recovery email flow with deep-link checkout |
| [`wishlist`](plugins/installed/wishlist/) | Customer + guest wishlists with shareable links |
| [`b2b`](plugins/installed/b2b/) | Quotes + per-account price lists + Net 15/30/45/60/90 |

#### Infra / Ops

| Plugin | What it does |
|---|---|
| [`analytics`](plugins/installed/analytics/) | Sessions, events, daily metric rollups, funnel definitions |
| [`observability`](plugins/installed/observability/) | Per-merchant `MerchantMetric` rollups, `ErrorEvent` log, GraphQL series API |
| [`environments`](plugins/installed/environments/) | Dev / staging / prod with snapshots + promotion |
| [`webhooks_ui`](plugins/installed/webhooks_ui/) | Endpoint CRUD + delivery log with retry / replay; HMAC-SHA256 signed |
| [`backups`](plugins/installed/backups/) | Scheduled `morph_backup` + restore tooling |
| [`cloudflare`](plugins/installed/cloudflare/) | DNS, cache purge, WAF, R2 — auto-purge on `product.updated` |
| [`tracking`](plugins/installed/tracking/) ★ | **GA4 + GTM control center** — server-side Measurement Protocol v2 on the hook bus (ORDER_PAID / ADD_TO_CART / BEGIN_CHECKOUT / view_item / search / signup / login), client-side GTM with **Consent Mode v2 defaults emitted before the container loads** (the #1 EEA-compliance bug per Google's own docs), storefront consent banner, audit log, container export |
| [`demo_data`](plugins/installed/demo_data/) | `manage.py morph_seed_demo` + theme-aware on-demand random product generator |

★ = recently added.

### First-party theme

| Theme | Stack |
|---|---|
| [`dot_books`](themes/library/dot_books/) | Modern editorial bookstore — vanilla HTML5 + plain CSS variables, Fraunces + Inter, **no Tailwind, no build step**. ~2 KB CSS gzipped. Active by default. |

---

## The agent layer

This is what makes Morpheus different from every other open-source commerce platform.

### 1. The Assistant (always-on, hard-coded)

[`core/assistant/`](core/assistant/) defines a single `Assistant` class. Mounted at `/dashboard/assistant/`. Reachable even when plugins explode. JSONL fallback persistence at `/tmp/morpheus-assistant/` when the DB is down.

**20 first-class tools** out of the box:

| Domain | Tools |
|---|---|
| **Reads — Ecommerce** | `orders.search`, `orders.get`, `recent_orders`, `products.search`, `products.get`, `customers.search`, `customers.get`, `analytics.summary`, `analytics.top_products`, `cms.pages`, `email.templates`, `media.search`, `metafields.list_for` |
| **Reads — System** | `db.list_models`, `db.describe_model`, `db.count_rows`, `settings.list` (secrets auto-redacted), `fs.read_file`, `fs.list_dir`, `fs.search_files`, `logs.recent_errors`, `logs.search`, `system.info`, `system.disk`, `system.git_log` |
| **Writes — gated by `confirmed=True`** | `orders.update_status`, `orders.cancel`, `orders.add_note`, `products.update_status`, `products.update_price`, `customers.add_note`, `cms.publish_page`, `cms.unpublish_page`, `metafields.set`, `metafields.delete` |
| **Plugins** | `plugins.list`, `plugins.enable`, `plugins.disable` (require approval) |
| **Delegate** | `delegate.invoke_agent` — route to a specialised agent for domain-specific work |

A floating chat widget is included on every admin page via the `{% morph_ask %}` template tag, with auto-context derived from `request.path`.

### 2. The Kernel (`core/agents/`)

A peer of `core/hooks` and `plugins/`. The substrate every agent (built-in or plugin-contributed) builds on:

```python
from core.agents import (
    MorpheusAgent, Tool, ToolResult, tool, Skill,
    AgentRuntime, LLMProvider, get_llm_provider,
    AgentTrace, agent_registry, skill_registry,
)
```

Concepts:

- **`MorpheusAgent`** — base class. Declare `name`, `label`, `audience` (`storefront` / `merchant` / `system` / `any`), `scopes`, `prompt_name`, `provider`, `model`, `default_tools`, `uses_skills`. **Brand voice fragment is auto-prepended to the system prompt** so every agent matches the merchant's tone.
- **`Tool`** — a single capability with a JSON Schema, scope list, and an optional `requires_approval` gate. Decorated with `@tool(...)`.
- **`Skill`** — a labeled bundle of tools + an optional system-prompt prelude. Plugins ship skills via `contribute_skills()`.
- **`AgentRuntime`** — real LLM tool-use loop with **failure isolation** — a single tool exception becomes a recoverable LLM message, not a crash.
- **`LLMProvider`** — abstraction over OpenAI / Anthropic / Gemini / OpenRouter / Ollama / Mock.
- **Hook integration** — `hook_registry.filter(AgentEvents.TOOL_CALLING, value=args, …)` runs before every tool call so plugins can transform or veto args.
- **Trace** — every run captures every step. Persisted to `AgentRun` + `AgentStep` rows by `agent_core` for a lossless audit trail.

### 3. Built-in agents (shipped by `agent_core` + `crm`)

| Agent | Audience | What it does |
|---|---|---|
| **Concierge** | storefront | Helps shoppers — searches catalog, recommends, answers product questions |
| **Merchant Ops** | merchant | Admin assistant — runs reports, drafts emails, queries the DB through tools |
| **Pricing** | system | Reviews and adjusts prices via the `product.calculate_price` hook |
| **Content Writer** | merchant | Generates SEO copy, product descriptions, blog posts |
| **Account Manager** | merchant | (CRM) Surfaces deal stage changes, follow-up tasks, lead-to-customer journeys |

### 4. Background agents

[`/dashboard/agents/background/`](https://dotbooks.store/dashboard/agents/background/)

Schedule any registered agent to run autonomously on a fixed interval. Backed by `BackgroundAgent` model + Celery beat (fires every minute). After `max_failures_before_pause` consecutive failures (default 5) an agent auto-pauses so a broken job can't burn through tokens. Reschedules **before** fire so concurrent beats can't double-run.

### 5. Observability dashboard

[`/dashboard/agents/observability/`](https://dotbooks.store/dashboard/agents/observability/) — per-agent runs / tokens / tool calls / avg duration over a configurable window, state breakdown, top tools, recent failures linking to run detail.

---

## Agentic commerce surfaces

External AI clients (Claude, ChatGPT, Perplexity, Copilot) can transact through Morpheus without per-vendor integrations.

### MCP server cluster (4 endpoints, Shopify-shape)

The [`agent_mcp`](plugins/installed/agent_mcp/) plugin stands up a JSON-RPC 2.0 endpoint compatible with the [Model Context Protocol](https://modelcontextprotocol.io). One dispatcher, four audience-scoped endpoints:

```text
POST /mcp/storefront/v1/  — anonymous catalog reads (no auth)
POST /mcp/cart/v1/        — same + cart manipulation
POST /mcp/checkout/v1/    — same + checkout
POST /mcp/admin/v1/       — Linda's full tool catalog (Bearer auth)
POST /mcp/v1/             — legacy curated-reads alias (backward-compat)
```

Each cluster scopes the tool whitelist to its audience via thread-local state, so the same dispatcher serves all four with per-request safety.

### UCP + Trusted Agent discovery

```text
GET /.well-known/ucp.json     — Universal Commerce Protocol manifest
                                (Google / Shopify / Stripe / Etsy / Walmart)
GET /.well-known/agent.json   — Visa Trusted Agent Protocol + Mastercard
                                Verifiable Intent acceptance
```

The `TrustedAgentMiddleware` reads `X-Verified-Agent-*` headers (set by Cloudflare's Web Bot Auth at the edge), attaches `request.trusted_agent`, and stamps `Order.metadata.agent_id` at checkout — so merchants get an auditable trail of which agent placed which order.

**Curated tool surface (legacy `/mcp/v1/`).** Only read tools safe for a public AI agent (search/fetch products, orders, analytics, content). Write tools and admin reads are **never** reachable here.

**Resources.** Three pre-defined entry-point URIs MCP clients can hit without learning the tool catalog:

```
morpheus://catalog/featured   — featured products
morpheus://catalog/recent     — newest 20 products
morpheus://analytics/today    — today's revenue + orders summary
```

Full integration guide: [`docs/AGENT_PROTOCOLS.md`](docs/AGENT_PROTOCOLS.md).

### Brand voice config

[`/dashboard/settings/ai/`](https://dotbooks.store/dashboard/settings/ai/) — set `brand_name`, `brand_audience`, `brand_tone`, `brand_voice_guidelines` once. The fragment is automatically prepended to:

- The dashboard's `call_llm()` helper (product description drafts, email rewrites, …)
- Every agent's system prompt via `MorpheusAgent.get_system_prompt()`

One edit, propagated everywhere — Shopify's "Magic" parity from a single config screen.

### Authoritative cart totals

[`orders.cart_totals`](plugins/installed/orders/graphql/queries.py) GraphQL query returns the canonical `(subtotal, shipping, tax, discount, total)` for any cart + address — used by the storefront and any external AI agent that wants to quote a price before checkout. Driven by the same `OrderService.calculate_cart_breakdown()` that runs at order create, so quotes match charges exactly.

---

## Saleor parity

A live tracker of how Morpheus compares to Saleor, the previous open-source benchmark.

| Capability | Saleor | Morpheus |
|---|---|---|
| Plugin architecture | ✅ | ✅ (`plugins/installed/`) |
| GraphQL API | ✅ | ✅ (Strawberry) |
| REST API | ❌ | ✅ (DRF) |
| Multi-channel + per-channel pricing | ✅ | ✅ (`core.StoreChannel` + `ProductChannelListing`) |
| Multi-currency | ✅ | ✅ (`core.ExchangeRate` + display currency context) |
| Translations | ✅ | ✅ (`core.i18n` — generic-FK `Translation` rows) |
| Payment gateway abstraction | ✅ | ✅ (`PaymentGateway` ABC + `GatewayRegistry`) |
| Promotion engine (rule-based) | ✅ | ✅ (`promotions` plugin — predicates × actions) |
| Draft orders / quotes | ✅ | ✅ (`draft_orders` plugin) |
| Multi-warehouse stock allocation | ✅ | ✅ (`inventory.allocator.plan_allocation`) |
| RBAC / permissions | ✅ | ✅ (`rbac` plugin — capabilities) |
| Webhooks (signed, retry/replay) | ✅ | ✅ (HMAC-SHA256, `webhooks_ui` plugin) |
| Audit log | ✅ | ✅ (`core.audit` — tamper-evident) |
| Bulk CSV import / export | partial | ✅ (`importers`) |
| **Shopify migration** | ❌ | ✅ (`importers/shopify` — REST + UI form) |
| Backups (pg_dump + media) | manual | ✅ (`manage.py morph_backup`) |
| **Metafields on every model** | ❌ | ✅ (`metafields` — GenericForeignKey) |
| **Central media library** | ❌ | ✅ (`media` — `MediaAsset` + picker) |
| **Hard-coded Assistant w/ 20 tools** | ❌ | ✅ |
| **Kernel agent layer (tool-use loop, scopes, trace)** | ❌ | ✅ |
| **MCP server (external AI client wire)** | ❌ | ✅ (`agent_mcp` — JSON-RPC 2.0) |
| **Brand voice config (one place, every generation)** | ❌ | ✅ (`ai_content`) |
| **Background agents (scheduled autonomous runs)** | ❌ | ✅ |
| **Skills (reusable tool bundles)** | ❌ | ✅ |
| **Agent observability dashboard** | ❌ | ✅ |
| **Agent-readable commerce surface (`/llms.txt`, agent receipts, agent GraphQL)** | ❌ | ✅ |
| **Plugin crash isolation** | ❌ | ✅ (broken `ready()` doesn't take down siblings) |

---

## Where Saleor is still better (honest)

We won't pretend. Saleor has ~5 years of production mileage on thousands of stores; Morpheus is younger. If you're picking a platform today, here's the candid trade-off so you can choose with eyes open:

| Area | Reality |
|---|---|
| **Maturity & runtime hours** | Saleor has shipped through edge cases Morpheus hasn't seen yet. Recent internal audits surfaced real concurrency bugs (promotion `usage_limit` race, gift-card redemption inside a broad except, refund-state race) that Saleor patched years ago. We're closing them — see [`CHANGELOG.md`](CHANGELOG.md) — but the lead is real. |
| **GraphQL completeness** | Saleor's GraphQL *is* the API — exhaustive, versioned, with announced breaking-change cadence. Morpheus has GraphQL for catalog/orders/cart but plenty of operations still live in Django views. Building a non-trivial headless storefront against Morpheus today means mixing GraphQL + REST + occasional template scraping. |
| **Multi-warehouse / multi-currency depth** | Saleor has stock-reservation across warehouses, channel-specific pricing, country-specific tax stacks, FX-aware refunds at multiple rate snapshots. Morpheus has the basics, not the edges. |
| **Public API contract** | Saleor's schema is versioned; Morpheus has no public-API stability guarantee yet. We're working on that ([`docs/API_STABILITY.md`](docs/API_STABILITY.md)) but you can't build a third-party app on Morpheus today and assume the schema won't shift. |
| **Performance at scale** | Saleor has been load-tested and tuned (caching layers, optimized indexes, CDN strategies). Morpheus hasn't published p95 numbers at 100 req/s yet. |
| **Developer ecosystem** | Stack Overflow questions, third-party tutorials, hosted-app marketplace, recruiters who know the name. Morpheus is one team — that's changing, but it's the truth today. |
| **Enterprise compliance posture** | Saleor Cloud has GDPR / PCI / SOC2 work done. Morpheus ships the `rbac` + `audit` + `observability` plugins but no third-party attestations. |
| **Webhook ecosystem** | Saleor webhooks have Zapier / Make / n8n recipes. Morpheus has the `webhooks_ui` plugin with the same primitives but the third-party recipe library is still thin — see [`docs/WEBHOOK_RECIPES.md`](docs/WEBHOOK_RECIPES.md) for the starters. |

**One-line summary**: Morpheus is the better pick for a new merchant launching this year with a small/mid catalog and a desire for AI-driven onboarding. Saleor is the safer pick for a $50M+ GMV merchant migrating off Shopify Plus today. We're working on closing both gaps — track progress in the [enterprise roadmap](ENTERPRISE_ROADMAP.md).

---

## Showcase

Five places in the codebase that earn the "advanced" claim:

### 1. Plugin crashes can't take the platform down

[`plugins/registry.py`](plugins/registry.py) — every contribution is collected in a try/except so a broken plugin is logged + isolated, sibling plugins keep loading, the platform keeps booting:

```python
def _activate(self, plugin: MorpheusPlugin) -> None:
    try:
        plugin.ready()
    except Exception as e:  # noqa: BLE001 — bad plugin must not bring down the app
        logger.error('Failed to activate plugin %s: %s', plugin.name, e, exc_info=True)
        return
    self._active.add(plugin.name)
    self._collect_contributions(plugin)
```

Shopify and Saleor have nothing comparable — a third-party app crash there can destabilise the request path.

### 2. The agent runtime sends every tool call through the hook bus

[`core/agents/runtime.py`](core/agents/runtime.py) — plugins can transform or veto tool args without monkey-patching:

```python
args = hook_registry.filter(
    AgentEvents.TOOL_CALLING, value=dict(tc.arguments or {}),
    agent=self.agent.name, tool=tc.name, run_id=run_id,
)
```

This is how scope policies, audit log writes, brand-voice injection, and rate limits all attach without each owning a runtime patch.

### 3. Metafields work on every Django model out of the box

[`plugins/installed/metafields/models.py`](plugins/installed/metafields/models.py) — one table, GenericForeignKey, all your custom data:

```python
class Metafield(models.Model):
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.CharField(max_length=64, db_index=True)
    target = GenericForeignKey('content_type', 'object_id')
    namespace = models.CharField(max_length=80, blank=True, default='')
    key = models.CharField(max_length=120)
    value = models.TextField(blank=True, default='')
    value_type = models.CharField(max_length=20, choices=VALUE_TYPES, default='string')

    class Meta:
        unique_together = [('content_type', 'object_id', 'namespace', 'key')]
```

`Metafield.objects.set(product, namespace='catalog', key='warranty_months', value=24, value_type='integer')` is idempotent. Inline editor drops into any form's sidebar via `{% include "metafields/_inline_editor.html" with object_model="..." object_id=... %}`.

### 4. Money arithmetic is quantised at every step

[`core/money.py`](core/money.py) — every operation returns a `CENTS`-quantized `Money`. `CurrencyMismatch` raised loudly. No rounding errors propagate:

```python
def quantize(value: MoneyLike, *, currency: str | None = None) -> Money:
    amount = _decimal_of(value).quantize(CENTS, rounding=ROUND_HALF_UP)
    if currency is None:
        currency = _currency_of(value)
    return Money(amount, currency)

def add(a: MoneyLike, b: MoneyLike) -> Money:
    cur = _currency_of(a)
    if _currency_of(b) != cur:
        raise CurrencyMismatch(f'add({cur} + {_currency_of(b)})')
    return quantize(_decimal_of(a) + _decimal_of(b), currency=cur)
```

### 5. Outbox events safely serialise Models + Money

[`core/hooks.py`](core/hooks.py) — domain events written in the same DB transaction as mutations, then a worker publishes them to NATS. The custom encoder turns Models into stable `{id, model}` dicts and Money into `{amount, currency}` so the outbox payload is always portable:

```python
class WebhookEncoder(DjangoJSONEncoder):
    def default(self, o):
        if isinstance(o, models.Model):
            return {'id': str(o.pk), 'model': o.__class__.__name__}
        if hasattr(o, 'amount') and hasattr(o, 'currency'):  # MoneyField
            return {'amount': str(o.amount), 'currency': str(o.currency)}
        return super().default(o)
```

---

## Architecture cheat sheet

```
   Plesk Nginx (TLS)        Coolify Traefik           Morpheus
       ↓                          ↓                        ↓
  HTTPS in 443  →  HTTP :80  →  routes by Host  →  gunicorn (web)
                                                  ↓
                                          ┌───────┼────────┐
                                          ▼       ▼        ▼
                                       redis   postgres   celery worker + beat

  Hooks fired in `core/hooks.py`
  └─→ writes to OutboxEvent (transactional)
        └─→ Celery `process_outbox` publishes to NATS JetStream + remote webhooks
        └─→ HMAC-SHA256 signature on every webhook (X-Morpheus-Signature)
```

Every domain transition (`order.placed`, `product.updated`, `agent.intent.completed`, …) is **both** dispatched in-process to local hooks **and** persisted to the outbox for at-least-once delivery to remote subscribers.

---

## Production observability (built in)

- **Request ID** — every response carries `X-Request-ID`. Every log line includes it. Sentry events include it.
- **Structured logs** — JSON in production, pretty in DEBUG. See [`core/log_formatters.py`](core/log_formatters.py).
- **OpenTelemetry** — auto-instruments Django, Celery, Redis, Postgres when `OTEL_EXPORTER_OTLP_ENDPOINT` is set. Fail-soft if the OTel libs aren't installed.
- **Sentry** — no-op until you set `SENTRY_DSN`. When set, scrubs auth tokens, cookies, password / secret / token / card from every event. See [`core/sentry.py`](core/sentry.py).
- **Errors are masked** — unhandled exceptions in DRF or GraphQL never leak stack traces. They get a stable error envelope with the request id and are written to the merchant `ErrorEvent` log.
- **Audit log** — `core.audit.record(...)` writes a tamper-evident `AuditEvent` row for security-grade events (RBAC grants, agent approvals, gateway changes).
- **Celery deadletter** — failed tasks land in `morpheus:deadletter:<task_id>` in Redis (7-day TTL).
- **MerchantMetric rollups** — hourly + daily Celery beat jobs roll `OutboxEvent` rows into time-series buckets. Query via `metricSeries(metric, granularity, hours)` GraphQL.
- **Agent observability** — per-agent runs / tokens / tool calls / avg duration at `/dashboard/agents/observability/`.
- **Real merchant analytics** — `/dashboard/analytics/` ships KPI tiles + sparklines + daily revenue line chart + top products + customers + day-of-week + hour-of-day patterns, **none of it gated behind a tier**.

---

## Scaffolders

```bash
python manage.py morph_create_plugin <name> [--with-models --with-graphql --with-urls --with-tasks]
python manage.py morph_create_theme  <name> [--from dot_books]
python manage.py morph_seed_demo            [--currency USD] [--fresh]
python manage.py morph_import shopify       --shop=… --token=…
python manage.py morph_import woocommerce   --base-url=… --consumer-key=… --consumer-secret=…
python manage.py morph_backup               [--dest /var/backups/morpheus] [--keep 7]
```

---

## Tech stack

- **Backend:** Python 3.12, Django 6
- **API:** Strawberry GraphQL + Django REST Framework + JSON-RPC 2.0 (MCP)
- **Database:** PostgreSQL — Supabase recommended; SQLite only for tests
- **Cache + queue:** Redis, Celery (`time_limit` / `soft_time_limit` / `acks_late`)
- **Event bus:** NATS JetStream (transactional outbox publisher)
- **LLM providers:** OpenAI / Anthropic / Gemini / OpenRouter / Ollama / Mock — selected by ai_assistant config
- **Observability:** OpenTelemetry → OTLP collector → Prometheus / Grafana / Loki + Sentry
- **Containers:** multi-stage Dockerfile, non-root, gunicorn runtime, k8s manifests
- **SDK:** [`services/sdk_python`](services/sdk_python/) — `pip install -e services/sdk_python`

---

## Security defaults (changed from a vanilla Django template)

- `DEBUG = False` by default. `SECRET_KEY`, `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`, `DATABASE_URL` are required in non-test envs.
- DRF default permission is `IsAuthenticated`; storefront catalog opts in to `AllowAny` explicitly.
- All webhooks ship with `X-Morpheus-Signature: sha256=<hmac>`.
- GraphQL has depth + alias caps (`GRAPHQL_MAX_QUERY_DEPTH`, `GRAPHQL_MAX_ALIASES`) and a `_MaskUnhandledErrors` extension.
- DRF + GraphQL exception handlers mask 5xx, surface `request_id`.
- `RateLimitMiddleware` wired on `/graphql` and `/v1/`. **Per-user rate limit on the agent invoke endpoint** (20 req/min/user). MCP endpoint same shape.
- `IGNORE_EXCEPTIONS` on Redis cache — a Redis blip can't 500 the site.
- `SECURE_PROXY_SSL_HEADER` set to honor `X-Forwarded-Proto` from Plesk / Traefik / any TLS terminator.
- Sentry `before_send` scrubs auth tokens, cookies, and any password / secret / token / card key.
- **`@safe_db` decorator** for paths where DB outage should degrade gracefully (audit logging, telemetry mirroring) instead of crashing the request.
- **RBAC capabilities** — `rbac.has_capability(user, 'orders.refund', channel=ch)` for fine-grained access checks. Grants/revokes are audit-logged.
- **Assistant write tools require `confirmed=True`** — the LLM can't mutate state without explicit user approval; the system prompt enforces the two-step pattern.
- **`settings.list` redacts secrets** — any plugin config key matching `*_key`, `*_secret`, `*_password`, `*_token` is auto-truncated before reaching the LLM.

---

## Documentation

- [`SKILLS.md`](SKILLS.md) — **named procedures** for every common task (add a plugin, fix N+1, deploy to Coolify, …). Start here.
- [`docs/PLUGIN_DEVELOPMENT.md`](docs/PLUGIN_DEVELOPMENT.md) — full plugin developer guide.
- [`docs/THEME_DEVELOPMENT.md`](docs/THEME_DEVELOPMENT.md) — full theme developer guide.
- [`docs/deploy-coolify.md`](docs/deploy-coolify.md) — Coolify deployment.
- [`docs/deploy-plesk-nginx.md`](docs/deploy-plesk-nginx.md) — Plesk Nginx → Coolify Traefik reverse proxy config.
- [`docs/OPERATIONS_RUNBOOK.md`](docs/OPERATIONS_RUNBOOK.md) — backups, restore, deploy chain, on-call basics.
- [`RULES.md`](RULES.md) — the platform's immutable laws. Read before PR.
- [`ARCHITECTURE.md`](ARCHITECTURE.md) — system design, plugin lifecycle, the four pillars.
- [`AI_VISION.md`](AI_VISION.md) — strategic thesis.
- [`CHANGELOG.md`](CHANGELOG.md) — every shipped PR by phase.

---

## Contributing

PRs welcome. The bar:

1. **New behavior comes with tests.** The whole suite is fast — keep it that way.
2. **Don't add a top-level Django app for a new domain — make it a plugin** ([Skill: add a new plugin](SKILLS.md#skill-add-a-new-plugin)).
3. **Don't catch broad `Exception` without `exc_info=True` + a one-line reason.**
4. **Honor the security defaults** in [`morph/settings.py`](morph/settings.py).
5. **Operational pages → main sidebar; persistent config → settings panel.** Don't pollute settings with operational knobs.
6. **The change is reachable from a [skill in `SKILLS.md`](SKILLS.md)** — add or update one in the same PR if it isn't.
7. **Write tools take `confirmed: bool`** — anything that mutates state through the assistant runtime must refuse without explicit confirmation.

---

## What's new (recent waves)

- **One-prompt store bootstrap** — new [`store_bootstrap`](plugins/installed/store_bootstrap/) plugin. Merchant types one sentence at `/dashboard/apps/store_bootstrap/start/`; the active LLM gateway returns a strict-JSON plan (brand voice + 4-6 categories + 10-12 products); platform writes everything in ~20 seconds. Idempotent on SHA-256 of the prompt, JSON-repair pass for trailing commas + unescaped newlines + code fences, `Category.get_or_create` so re-runs don't duplicate.
- **GA4 + GTM tracking plugin** — new [`tracking`](plugins/installed/tracking/) plugin. Server-side Measurement Protocol v2 firing on the hook bus (ORDER_PAID / ADD_TO_CART / BEGIN_CHECKOUT / view_item / view_item_list / search / signup / login / refund), client-side GTM container with **Consent Mode v2 defaults emitted before the container script** (the #1 EEA-compliance bug per Google's own docs), storefront consent banner, dashboard control center at `/dashboard/tracking/` with Connection / Events / Consent / Identity / Filters / Tests tabs.
- **Money-path concurrency hardening** — Stripe webhook now writes to the previously-unused `StripeWebhookEvent` table first; the unique constraint on `stripe_event_id` turns retried deliveries into IntegrityError → "already processed". `_mark_transaction_failed` mirrors the success path with `atomic()` + `select_for_update()` + terminal-state short-circuit. Audit trail covers every webhook delivery with `is_processed` + `processed_at` + `error`.
- **Shared LLM-JSON parser** — `core.llm_parsing.parse_llm_json` is the single canonical "extract JSON from an LLM response" helper. Three near-identical parsers across `store_bootstrap`, `populate_descriptions`, `generate_pdp_faqs` are now one shared implementation with code-fence stripping + outermost-block detection + trailing-comma + literal-newline repair. The two older callers inherit the robustness.
- **Bootstrap as its own plugin** — `store_bootstrap` was extracted out of `admin_dashboard` per the architectural compass. Plugin manifest declares `requires=[catalog, ai_assistant, ai_content]`, contributes its own `DashboardPage`, registers URLs at the standard `dashboard/apps/<plugin>/` prefix.
- **2026 SEO + AEO rebuild** — Per-bot AI crawler matrix in robots.txt (15 bots: GPTBot, ClaudeBot, PerplexityBot, Google-Extended, Bytespider, Applebot-Extended, Meta-ExternalAgent, CCBot, …); markdown export at `/md/products/<slug>` so LLM crawlers skip HTML parsing; sitemap-index + sitemap-news + sitemap-images; IndexNow auto-push on product save (Bing/Yandex/Naver/Seznam/Yep); `manifest.json` + `opensearch.xml`; Speakable + ProductGroup + MerchantReturnPolicy + shippingDetails + gtin13 + brand + author + sameAs on every PDP; Twitter `label1/data1` + OG `product:price:amount` so Slack/iMessage/Discord previews render price + availability inline; **Core Web Vitals RUM** via `web-vitals@4` beacon → audit log → dashboard p75 panel.
- **2026 AEO content-quality audit** — new rules in `seo.services.audit_product`: thin description (<100 words → AI search cites long-form 10× more), missing internal links, generic alt text (`image`/`photo`/`cover`/duplicate of product name), no H2/H3 subheadings in long bodies, missing `dateModified` from `Product.updated_at` (Perplexity decays citations after ~13 weeks). Content-quality penalty capped at -25 collectively so it nudges rather than swamps the score. New `manage.py backfill_alt_text` builds content-aware `"{title} by {author} — book cover"` alts in bulk.
- **Image optimization kit** — Pillow-backed on-the-fly WebP/AVIF generation at `/img/<fmt>/<width>/<path>` with 1-year immutable cache; `{% seo_responsive_image %}` template tag emits `<picture>` with AVIF + WebP `<source>` + JPEG fallback; supports `priority=True` (LCP + fetchpriority=high), `view_transition_name` (preserves PLP→PDP morphs), and `img_id` (PDP gallery thumbnail swap rewrites both source srcsets and `<img>` src). 35–39 % byte reduction on existing covers without any pre-build step.
- **Checkout WCAG 2.2 AA refresh** — Visible `<label for>` above every input (placeholder-as-label retired); `role="alert" aria-live="assertive"` error summary at the top of the form with auto-focus on submit fail; full `autocomplete` token set + `inputmode` per field; `aria-busy` + defensive timeout on the submit button; 48 px inputs (≥ AA target size); `:focus-visible` 2 px outline @ 3:1 contrast.
- **Linda assistant page redesign** — Sidebar widget removed; borderless single-column chat; sticky bottom textarea (auto-grows, Enter sends, Shift+Enter newline); circular dark send button; centred empty state with starter chips; page itself never scrolls (only the log).
- **Dashboard partial reload** — htmx@2 wired on the admin shell. Sidebar + topbar excluded so cross-section navigation keeps server-rendered active-state; filter/sort/pagination forms inside `<main>` swap only the content panel. View Transitions API integration for native crossfade between swaps. Progress bar across the top during a request.
- **Grok (xAI) provider** — Sixth LLM provider alongside OpenAI / Anthropic / Gemini / OpenRouter / Ollama. OpenAI-compatible at `https://api.x.ai/v1`. Registered in both `core.agents.llm` (kernel) and `plugins.installed.ai_assistant.services.llm` (content/draft path) — same key, both surfaces.
- **Agentic-commerce wave** — MCP server (`agent_mcp`), assistant write tools (8 gated capabilities), authoritative `cart_totals` GraphQL, Shopify migration UI, brand voice config flowing into every AI generation.
- **Foundations wave** — `media` plugin (central asset library + embeddable picker), `metafields` plugin (schema-less custom fields with inline editor), `metafields ↔ media` integration via `value_type='file_id'`.
- **Shopify-pattern dashboard wave** — sticky save/discard bar with dirty-form detection, status tabs, sortable column headers, real pagination, per-row overflow action menus, two-column product form with sidebar, setup checklist progress meter, real analytics page (KPIs + line chart + breakdowns).

See [`CHANGELOG.md`](CHANGELOG.md) for the full history.

---

## License

MIT. Build whatever you want with it.

<div align="center">
<sub>Built by people who think AI agents deserve a real commerce platform, not a chatbot tab.</sub>
</div>
