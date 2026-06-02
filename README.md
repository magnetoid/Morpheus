<div align="center">

# Morpheus OS

### A modular, plugin-native ecommerce platform.

**Catalog → cart → checkout → fulfillment in a tiny core. Everything else is a plugin.**

Open source · Plugin-native · Event-sourced · Production-grade · AI-native

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Live demo](https://img.shields.io/badge/live-dotbooks.store-ff5722.svg)](https://dotbooks.store)
[![Plugins](https://img.shields.io/badge/plugins-60%2B%20active-blue.svg)](#whats-inside)
[![Modular](https://img.shields.io/badge/modular-theme%20slots%20%E2%86%92%20plugin%20fills-06b6d4.svg)](#the-modularity-contract)
[![MCP](https://img.shields.io/badge/MCP-ready-7c3aed.svg)](#agentic-commerce-surfaces)
[![SEO / AEO](https://img.shields.io/badge/SEO%20%2B%20AEO-2026%20stack-eab308.svg)](#discovery--seo--aeo)
[![One-prompt bootstrap](https://img.shields.io/badge/bootstrap-1%20prompt%20%E2%86%92%20live%20store-22c55e.svg)](#one-prompt-store-bootstrap)
[![Stack](https://img.shields.io/badge/django%206-postgres-2563eb.svg)](#tech-stack)

[Quick start](#quick-start) · [The mental model](#the-mental-model) · [The modularity contract](#the-modularity-contract) · [What's inside](#whats-inside) · [The agent layer](#the-agent-layer) · [Agentic commerce surfaces](#agentic-commerce-surfaces) · [Discovery / SEO / AEO](#discovery--seo--aeo) · [Roadmap](#roadmap) · [Showcase](#showcase) · [Docs](#documentation)

</div>

---

## What Morpheus is

**Morpheus OS is a modular ecommerce platform.** The core is small — catalog, cart, checkout, fulfillment, plus the handful of foundations everything depends on (auth, hooks, settings, i18n, observability, the safety boundary). *Everything else is a plugin:* reviews, loyalty, markets, CMS, SEO, payments gateways, the agent layer, the 3D storefront — all self-contained packages under [`plugins/installed/`](plugins/installed/) that you can enable, disable, or fork without touching the engine.

The defining principle is the **modularity contract**: a theme exposes named slots, plugins fill those slots with storefront blocks and dashboard pages, and **disabling a plugin removes its surfaces** — no dangling references, no half-wired features. See [The modularity contract](#the-modularity-contract).

**It's also AI-native.** Where most platforms bolt AI on as a third-party API consumer, Morpheus treats agents as a first-class audience: a hard-coded merchant Assistant in `core/`, a real agent kernel, and a multi-protocol gateway (MCP, UCP, Trusted-Agent) so external AI clients can transact directly. That's a genuine strength — but it sits *on top of* a complete commerce platform, not in place of one.

### How it compares

Saleor, Medusa, and Vendure are excellent self-hostable platforms. Morpheus's bet is **plugin-native modularity plus a built-in agent layer**: the multi-protocol agent gateway that Shopify Sidekick, Adobe Commerce, and BigCommerce are racing toward ships here today, behind toggleable plugins rather than a hosted add-on.

| Capability | Morpheus | Saleor | Medusa | Vendure |
|---|:---:|:---:|:---:|:---:|
| MCP server cluster (storefront / cart / checkout / admin) | ✅ | — | — | — |
| Universal Commerce Protocol (`/.well-known/ucp.json`) | ✅ | — | — | — |
| Visa TAP + Mastercard VI acceptance (`/.well-known/agent.json`) | ✅ | — | — | — |
| Always-on hard-coded merchant assistant (Linda) | ✅ | — | — | — |
| Hybrid retrieval (BM25 + dense + RRF) on storefront search | ✅ | — | — | — |
| EU AI Act decision-provenance audit trail | ✅ | — | — | — |
| **Auto-generated Google Web Stories per product (AMP)** | ✅ | — | — | — |
| **AI-crawler-aware sitemap + 15-bot robots matrix + `/llms.txt`** | ✅ | — | — | — |
| **Per-product markdown export (`/md/products/<slug>`)** | ✅ | — | — | — |
| **AMP Web Story discovery (`<link rel="amphtml">` + sitemap)** | ✅ | — | — | — |
| **Auto-IndexNow ping on Product / Category / Collection / CMS save** | ✅ | — | — | — |
| Plugin-isolated runtime + first-party plugin catalog | ✅ | ✱ | ✱ | ✱ |
| GraphQL + signed webhook fanout | ✅ | ✅ | ✅ | ✅ |

(✱ = extension framework exists, no plugin-isolation guarantees comparable to Morpheus's `safe_db` + crash-isolation contract.)

**The platform is the product; the plugins are the surface.** Every model, hook, dashboard, and state transition is designed to be machine-actionable first and human-pretty second — which is what makes the AI layer feel native rather than bolted on. The Assistant is not a chatbot tab — it's a hard-coded operator in `core/` that survives plugin failure, has system-level scopes, **20+ tools spanning read and gated writes**, and can delegate to specialised agents that other plugins contribute. External AI clients reach the platform over a real **Model Context Protocol** server, with brand-voice config that propagates to every generation in the system.

What you get:

| Pillar | What it means in practice |
|---|---|
| **Plugin-native everything** | The default install ships 60+ plugins enabled (the source of truth is [`MORPHEUS_DEFAULT_PLUGINS`](morph/settings.py) — never a hard-coded count). Each contributes any of: storefront blocks, dashboard pages, settings panels, hooks, agents, agent tools, skills, URLs, GraphQL extensions, beat tasks. **Plugin crashes are isolated** — a broken `ready()` is logged and that plugin is excluded; siblings keep loading. |
| **Modularity contract** | A theme exposes named slots; plugins fill them; disabling a plugin removes its surfaces. The theme owns layout + CSS + which slots exist — that's the boundary. See [the contract](#the-modularity-contract), [`docs/PLUGIN_DEVELOPMENT.md`](docs/PLUGIN_DEVELOPMENT.md), and [`docs/THEME_DEVELOPMENT.md`](docs/THEME_DEVELOPMENT.md). |
| **Event-sourced + outbox** | Every state change emits a hook *and* writes to a transactional outbox shipped to NATS JetStream. Replayable, auditable, fanout-friendly. HMAC-SHA256 on every outbound webhook. |
| **Schema-less custom data** | A first-class [`metafields`](plugins/installed/metafields/) plugin: `(content_type, object_id, namespace, key, value)` triples on **any** Django model out of the box. The Shopify escape valve, but generic. |
| **Central media library** | A dedicated [`media`](plugins/installed/media/) plugin: one `MediaAsset` model, sharded uploads, kind tabs, embeddable picker — used everywhere a file ID is needed. |
| **Hard-coded Assistant in core** | A single Morpheus Assistant lives in [`core/assistant/`](core/assistant/) — never a plugin. **20 first-class tools** spanning filesystem, DB introspection, ecommerce reads (orders / products / customers / analytics / content / settings / media / metafields) and gated writes (orders.cancel, products.update_price, metafields.set, …). JSONL fallback persistence so the chat works even when the DB is unreachable. |
| **Kernel agent layer** | [`core/agents/`](core/agents/) is a peer of `core/hooks` and `plugins/`. Real LLM tool-use loop, provider abstraction (OpenAI / Anthropic / Gemini / OpenRouter / Grok / Ollama / Mock), versioned prompts, capability scopes, lossless trace, **Skills** (reusable tool bundles), background scheduling, **brand-voice-aware system prompts**. |
| **Agentic-commerce ready** | A first-class **MCP server cluster** exposes audience-scoped surfaces (storefront / cart / checkout / admin) to external AI clients via JSON-RPC 2.0, plus UCP + Trusted-Agent discovery at `/.well-known/`. Bearer-token auth on the admin surface, public reads everywhere else. |
| **AI-first discoverability** | A dedicated [`seo`](plugins/installed/seo/) plugin closes the **2026 SEO + AEO** loop end-to-end: 15-bot AI crawler matrix, per-object meta + JSON-LD (Product/Book/Review/Article/FAQ/QA/Breadcrumb/Organization), markdown export, `/llms.txt`, IndexNow, RSS+Atom journal feeds, hreflang, security.txt, sitemap index + image/news sub-sitemaps, paste-a-slug **SEO inspector**, sitemap truncation banner, 404→redirect manager. |
| **Google Web Stories** | A dedicated [`webstories`](plugins/installed/webstories/) plugin auto-generates a valid AMP `<amp-story>` document per product from images + book metafields. Embedded on the PDP via `<amp-story-player>`, surfaced to Google via `<link rel="amphtml">` + sitemap. Rebuilt automatically on product/image save. |

Live deployment: **https://dotbooks.store** · 60+ plugins (see [`MORPHEUS_DEFAULT_PLUGINS`](morph/settings.py)) · 1 generic Worker agent (specialised via skill bundles) · 1 hard-coded Assistant · 1 MCP server cluster · ~20-second one-prompt store bootstrap.

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
│   60+ enabled by default (source of truth: MORPHEUS_DEFAULT_PLUGINS).         │
│   Each is a self-contained Python package. Disable one → its surfaces vanish. │
│                                                                              │
│  COMMERCE          AI / AGENTS        DISCOVERY          INFRA / OPS          │
│  catalog           agent_core         seo  (2026 stack)  cloudflare           │
│  orders            agent_mcp          webstories         observability        │
│  customers         ai_assistant       pwa                environments         │
│  payments          ai_content         flipbook           webhooks_ui          │
│  advanced_payments functions          tracking           backups              │
│  inventory         store_bootstrap                       demo_data            │
│  tax                                  FOUNDATIONS         markets              │
│  shipping          GROWTH             media               localization        │
│  promotions        crm                metafields          bookvault            │
│  draft_orders      affiliates         importers           admin_dashboard     │
│  storefront        marketplace        rbac                advanced_ecommerce  │
│  gift_cards        marketing          notifications_      analytics           │
│  reviews           loyalty_points     center              product_gallery     │
│  subscriptions     wishlist                               product_videos      │
│  digital_products  cart_abandonment   STOREFRONT EXTRAS                       │
│  dynamic_products  workflows          lumina  (/create/)                      │
│                    personalisation    bookstore_3d  (/walkthrough/)           │
│                                       B2B / Workflows → b2b                    │
└──────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                              LAYER 3 — THEMES                                 │
│       Plugins ship features. Themes ship presentation. They never mix.       │
│                                                                              │
│  themes/library/dot_books/   ← active by default; modern editorial            │
│                                                                              │
│  A theme declares which slots exist + owns layout + CSS. Plugins contribute   │
│  via {% storefront_blocks "slot" %} into those slots. That's the boundary —   │
│  and it's the platform's defining principle. See "The modularity contract".  │
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

### Three non-obvious rules

1. **The Assistant is not a plugin.** Lives in `core/`. Survives plugin failure. Mounted at `/dashboard/assistant/` *before* the plugin URL prefix so it remains reachable even if every plugin import explodes. JSONL fallback persistence so the chat keeps working when the DB is down.
2. **Operational pages live in the main sidebar; persistent configuration lives in Settings.** Promotions, draft orders, demo-data generators — those are *operational pages* and surface under main-menu sections (Marketing / Sales / Catalog). Settings panels are reserved for things you set once: API keys, provider choice, on/off toggles.
3. **Every write goes through hooks.** `order.placed`, `product.updated`, `agent.intent.completed`, `cart.checkout.totals` — handlers can transform or veto. The agent runtime calls `hook_registry.filter(AgentEvents.TOOL_CALLING, …)` before every tool call so plugins can intercept.

---

## The modularity contract

This is the platform's defining principle. Read it once and the whole codebase makes sense.

> **A theme exposes named slots → plugins fill those slots → disabling a plugin removes its surfaces.**

A theme is *presentation only*: it owns the layout, the CSS, and — crucially — **declares which slots exist** (`pdp_above_long_description`, `nav_primary_extra`, `cart_summary_footer`, …). It ships no features. Plugins are *features only*: they contribute into those slots without ever editing a theme template.

```django
{# in a theme template — the theme decides this slot exists #}
{% storefront_blocks "pdp_above_long_description" %}
```

```python
# in a plugin's plugin.py — the plugin decides what goes in it
def contribute_storefront_blocks(self):
    return [StorefrontBlock(
        slot='pdp_above_long_description',
        template='webstories/_pdp_player.html',
        priority=20,
    )]
```

What this buys you:

- **Clean teardown.** Disable `webstories` and the `<amp-story-player>` block disappears from every PDP — no dangling include, no broken template, no orphaned URL. Disable `lumina` and the `/create/` route plus its nav link are simply gone. Same for `bookstore_3d`'s `/walkthrough/`. The platform keeps booting; the surface is just no longer there.
- **No cross-plugin coupling.** Plugins never import each other's models. They coordinate through the [`core.hooks`](core/hooks.py) event bus and contribute through slots — so two plugins can both target the same slot (ordered by `priority`) without knowing about each other.
- **Crash isolation.** A plugin whose `ready()` throws is logged and excluded; its slots stay empty and every sibling keeps loading. Modularity isn't just an organising idea — it's enforced at activation time.
- **Themes are swappable.** Because a theme only owns slots + presentation, you can fork [`dot_books`](themes/library/dot_books/) or ship a brand-new theme that exposes the *same* slot names, and every plugin lights up unchanged.

Full guides: [`docs/PLUGIN_DEVELOPMENT.md`](docs/PLUGIN_DEVELOPMENT.md) (the App SDK — manifest, contributions, hooks) and [`docs/THEME_DEVELOPMENT.md`](docs/THEME_DEVELOPMENT.md) (the Theme SDK — slots, layout, the dot_books reference).

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

### First-party plugins

The default install enables 60+ plugins — the canonical list is [`MORPHEUS_DEFAULT_PLUGINS`](morph/settings.py) (don't trust a count in prose; it rots). A representative tour by domain:

#### Commerce

| Plugin | What it does |
|---|---|
| [`catalog`](plugins/installed/catalog/) | Products, variants, categories, collections, attributes, vendors — `agent_metadata` on every Product |
| [`orders`](plugins/installed/orders/) | Cart → Order FSM, fulfillments, refunds, immutable `OrderEvent` log, **authoritative `cart_totals` GraphQL query** |
| [`customers`](plugins/installed/customers/) | Custom user + addresses + CDP fields (`lifetime_value`, `purchase_count`, `last_order_at`) |
| [`payments`](plugins/installed/payments/) | `PaymentGateway` ABC + `GatewayRegistry`. Stripe + Manual adapters; idempotent intents |
| [`advanced_payments`](plugins/installed/advanced_payments/) | Extra payment methods as modular gateways — a sandbox **test** gateway (always succeeds, for end-to-end checkout testing) + **cash on delivery** (`cod`). Registered into the same `GatewayRegistry`; disable to remove them from checkout |
| [`inventory`](plugins/installed/inventory/) | Stock movements, low/back-in-stock hooks, `allocator.plan_allocation()` for multi-warehouse splits |
| [`promotions`](plugins/installed/promotions/) | Rule-based engine — JSON predicates × actions (% off, fixed off, free shipping, gift, BOGO, tiered) |
| [`draft_orders`](plugins/installed/draft_orders/) | Quote / invoice flow — build a priced cart, share with customer, convert on payment |
| [`tax`](plugins/installed/tax/) | Regions + categorised rates (US sales tax / EU VAT / OSS); cart-total hook |
| [`shipping`](plugins/installed/shipping/) | Zones + rates (flat / weight / order-total tier / free-over / Shippo / EasyPost slots) — **real weight-unit conversion** |
| [`gift_cards`](plugins/installed/gift_cards/) | Issue / redeem / balance, append-only ledger, checkout-time discount |
| [`subscriptions`](plugins/installed/subscriptions/) | Plan + Subscription + invoice; Stripe Billing adapter slot |
| [`digital_products`](plugins/installed/digital_products/) | Token-gated downloads with expiry + count limits |
| [`dynamic_products`](plugins/installed/dynamic_products/) | Personalized merchandising blocks — for-you / related / recently-viewed `DynamicBlock`s contributed into storefront slots (PDP, cart, home) |
| [`reviews`](plugins/installed/reviews/) | Star ratings + verified-purchase signal |

#### AI / Agents

| Plugin | What it does |
|---|---|
| [`agent_core`](plugins/installed/agent_core/) | **Persistence + GraphQL + dashboard for the agent kernel.** Built-in agents (Concierge, Merchant Ops, Pricing, Content Writer). Background agents lifecycle + observability dashboard |
| [`agent_mcp`](plugins/installed/agent_mcp/) | **MCP server cluster** — JSON-RPC 2.0 endpoints (`/mcp/storefront/v1/`, `/mcp/cart/v1/`, `/mcp/checkout/v1/`, `/mcp/admin/v1/`, + legacy `/mcp/v1/`) so external AI clients can transact through Morpheus without per-vendor integrations. Also serves the `/.well-known/` UCP + Trusted-Agent discovery docs |
| [`ai_assistant`](plugins/installed/ai_assistant/) | AI provider config (OpenAI / Anthropic / Gemini / OpenRouter / **Grok (xAI)** / Ollama), embeddings, semantic search, recommendations, dynamic pricing. Per-provider key + model + live model picker from `/v1/models` |
| [`ai_content`](plugins/installed/ai_content/) | **Brand voice config** — single source of truth that propagates to every AI generation in the platform via `services.get_brand_voice()`. Tone, audience, guidelines edited once propagate to product copy, email rewrites, SEO drafts |
| [`store_bootstrap`](plugins/installed/store_bootstrap/) | **One-prompt store seed** — merchant describes a concept in one sentence, plugin generates brand voice + categories + 10-12 starter products in ~20s. Idempotent on SHA-256 of prompt. The AI-first onboarding moment |
| [`functions`](plugins/installed/functions/) | Sandboxed merchant-defined logic for cart totals, pricing, shipping, validation |

#### Foundations

| Plugin | What it does |
|---|---|
| [`media`](plugins/installed/media/) | **Central asset library** — single `MediaAsset` model, sharded uploads, kind tabs, embeddable picker, JSON upload API. **Federated view** unions library uploads + product images + digital-product files into one grid; click any asset for an inline **title / alt / description / SEO modal** + per-tile download. Replaces per-model `ImageField` proliferation |
| [`metafields`](plugins/installed/metafields/) | **Schema-less `(namespace, key, value)` triples on any record** via Django `GenericForeignKey`. Inline editor partial drops into any edit form sidebar |
| [`importers`](plugins/installed/importers/) | Idempotent migrators: **one-click Shopify CSV / Admin API import**, WooCommerce, fixture loader |
| [`seo`](plugins/installed/seo/) | **Full 2026 SEO + AEO stack.** Per-object meta with auto-flowing `seo_object` on PDP / category / collection / staff_picks. **JSON-LD:** `Product`, `Book` subtype (bookFormat, numberOfPages, inLanguage, datePublished, isbn from `book.*` metafields), `ProductGroup w/ hasVariant`, `Offer` with `MerchantReturnPolicy` + configurable `shippingDetails` window + gtin13 + brand + sameAs, `BreadcrumbList`, `SpeakableSpecification`, `CollectionPage` with `isPartOf`/`itemListOrder`/correct `numberOfItems`, `FAQPage`, **`QAPage`**, `Article` (publisher + `mainEntityOfPage` + conditional `dateModified` + `image_url`), **individual `Review` nodes** alongside `AggregateRating` — every block **toggleable from the SEO settings page** (no-code emission switches for Organization / WebSite / Product / Reviews), with Product `image` emitted as Google's recommended multi-photo array. **Sitemap:** `sitemap.xml` (covering products, categories, collections, vendors, **authors from metafields**, journal, static editorial routes, `/shipping/` + `/returns/` policy pages, manual entries) + `sitemap-images.xml` + `sitemap-news.xml` + `sitemap-index.xml`. Sitemap silently-truncates banner in dashboard when >50k entries. `xmlns:xhtml` declaration + `<xhtml:link rel="alternate" type="text/markdown">` per product. **`robots.txt`:** 15-bot AI crawler matrix (per-bot allow/disallow toggles for GPTBot / ClaudeBot / PerplexityBot / Google-Extended / Bytespider / Applebot-Extended / Meta-ExternalAgent / CCBot / Yandex/Bingbot/…) + advertises the sitemap-index. **`/llms.txt`** + **`/llms-full.txt`** with per-product `/md/` links. **Per-product markdown export** at `/md/products/<slug>` so LLM crawlers ingest copy without HTML. **IndexNow** auto-push on Product / **Category / Collection / CMS page** edits (Bing/Yandex/Naver/Seznam/Yep). **RSS 2.0 + Atom 1.0 journal feeds** at `/journal/feed.xml` + `/journal/atom.xml` with `<link rel="alternate">` from base. **`seo_hreflang`** templatetag emits `<link rel="alternate" hreflang="…">` per active Market + `x-default`. **`/.well-known/security.txt`** (RFC 9116). **OG + Twitter card** from live `StockLevel` aggregate (real `og:availability`). `/opensearch.xml` + `/manifest.json`. **Cache-Control + Last-Modified** on every public endpoint (sitemap/robots/llms/ai-feed/opensearch/news/images). **AI feed** `/ai/products.json` with `?offset=` pagination + `numberOfItems` + `nextPage`. **Dashboard:** Quick Actions (inline ping IndexNow), outcome-ratio KPIs (`meta_complete_pct`, `not_found_7d` delta, `keywords_in_top10`), audit table with drill-down (View PDP / Edit / Bulk-meta filter), `?q=`/`?missing=`/paginator on bulk-meta + char counters, **paste-a-slug SEO Inspector** rendering title/desc/canonical/robots/sitemap-presence/audit score/keyword matches/JSON-LD/OG in one card, **404 → redirects** manager with Dismiss action. **Core Web Vitals RUM** via `/web-vitals/` beacon → dashboard p75 panel. **On-the-fly WebP/AVIF image variants** at `/img/<fmt>/<width>/<path>` + `{% seo_responsive_image %}` template tag with priority + view-transition-name + gallery-swap support. |
| [`webstories`](plugins/installed/webstories/) | **Google Web Stories per product (AMP).** Generates a valid `<amp-story>` document from `Product.images` + `book.*` metafields on every product save and image change. PDP embed via `StorefrontBlock(slot='pdp_above_long_description')` renders an `<amp-story-player>` thumbnail; tap opens fullscreen. `<link rel="amphtml">` lands the story in Google Discover + the Web Stories carousel. Story URLs join the main `sitemap.xml`. Auto-build heuristic: cover panel with title + author byline → `short_description` over second image → remaining images with alt-text captions → optional "About this book" from `book.synopsis` → "Shop now" CTA. Prefers WebP variants. `python manage.py backfill_webstories` for one-shot population of an existing catalog. |
| [`rbac`](plugins/installed/rbac/) | Named roles + capabilities — 6 system role templates, `has_capability(user, cap, channel=None)`, audit-logged grants |

#### Storefront / Admin

| Plugin | What it does |
|---|---|
| [`storefront`](plugins/installed/storefront/) | Public storefront views, customer account v2 (orders, addresses, returns, profile), gift-card redemption |
| [`admin_dashboard`](plugins/installed/admin_dashboard/) | **Shopify-style merchant admin** — sticky save bar, status tabs, sortable columns, real pagination, per-row action menus, two-column edit forms, command palette, date-range picker, real analytics page (KPIs + line chart + breakdowns), staff account page |
| [`cms`](plugins/installed/cms/) | Pages (state machine) with a **WordPress-style editor** (TipTap rich text; create / edit / duplicate / delete; layout + schedule), a **Pages registry** that lists every storefront URL — CMS-managed *and* code-owned (the latter shown locked, "managed in code"), Blocks, Menus, Forms (submissions bridge into CRM as Lead+Interaction). Full **GraphQL + MCP** read/write surface for pages & blocks (gated `cms.read` / `cms.write`) |
| [`advanced_ecommerce`](plugins/installed/advanced_ecommerce/) | Recently viewed, free-shipping progress, low-stock badge, bulk price edit |

#### Storefront extras (show the modularity contract at its boldest)

| Plugin | What it does |
|---|---|
| [`lumina`](plugins/installed/lumina/) | Storefront landing page for the **Lumina Book Creator** — "write a book with AI + voice". Owns the `/create/` route and contributes a "Write a book" link into the theme's `nav_primary_extra` slot. Disable it and both the page and the nav link disappear. |
| [`bookstore_3d`](plugins/installed/bookstore_3d/) | An immersive first-person **3D bookstore walkthrough** at `/walkthrough/`, rendered inside the active theme (header / nav / footer) with a full-bleed three.js canvas loaded from a CDN importmap — **no build step**. Pure plugin: disable it and the route is gone. |
| [`flipbook`](plugins/installed/flipbook/) | Page-flip preview reader for digital book products |
| [`product_gallery`](plugins/installed/product_gallery/) · [`product_videos`](plugins/installed/product_videos/) | Richer PDP media — gallery lightbox + product video embeds, contributed via PDP slots |
| [`pwa`](plugins/installed/pwa/) | Installable + offline storefront — `manifest.webmanifest` + service worker (cache-first static, network-first pages) |

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
| [`tracking`](plugins/installed/tracking/) | **GA4 + GTM control center** — server-side Measurement Protocol v2 on the hook bus (ORDER_PAID / ADD_TO_CART / BEGIN_CHECKOUT / view_item / search / signup / login), client-side GTM with **Consent Mode v2 defaults emitted before the container loads** (the #1 EEA-compliance bug per Google's own docs), storefront consent banner, audit log, container export |
| [`demo_data`](plugins/installed/demo_data/) | `manage.py morph_seed_demo` + theme-aware on-demand random product generator |

> Not shown above (all real, all in [`MORPHEUS_DEFAULT_PLUGINS`](morph/settings.py)): `markets`, `localization`, `bookvault`, `notifications_center`, `workflows`, `personalisation`, `post_purchase`, `experiments`, `fraud_rules`, `trust_signals`, `consent`, `subscriptions`. Browse [`plugins/installed/`](plugins/installed/) for the full set.

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

## Discovery / SEO / AEO

The discovery surface a 2026 commerce platform actually needs. Built primarily by the [`seo`](plugins/installed/seo/), [`webstories`](plugins/installed/webstories/), [`tracking`](plugins/installed/tracking/), and [`pwa`](plugins/installed/pwa/) plugins. The whole thing is opinionated, observable, and gated by per-feature toggles — nothing here is theoretical.

### Crawler-facing endpoints

| Endpoint | What it serves | Why it matters |
|---|---|---|
| `/sitemap.xml` | Every active product, category, collection, vendor, author (derived from `book.author` metafields), journal entry, static editorial route, `/shipping/`, `/returns/`, story URLs — plus a banner in the dashboard when the **50 000-URL cap** is hit | The single source of truth for discovery |
| `/sitemap-index.xml` | Discovery doc that lists every sub-sitemap; advertised by `robots.txt` so crawlers find image / news / main from one URL | Replaces the previous flat single-sitemap shape |
| `/sitemap-images.xml` | Up to `_sitemap_max_urls()` product images with `<image:caption>` + `<image:title>` | Powers Google AI Overviews + Bing image grounding |
| `/sitemap-news.xml` | Journal entries within a configurable max-age window (default 7 days) | Google News + AI-citation discovery |
| `/robots.txt` | 15-bot AI-crawler matrix (per-bot allow/disallow toggle from the dashboard) + sitemap-index advertisement + `Cache-Control` | Per-bot policy — block GPTBot, allow ClaudeBot, throttle Bytespider, etc. |
| `/llms.txt` + `/llms-full.txt` | Site description + per-product `/md/` links for LLM crawlers | Cuts crawler HTML parsing overhead by ~10× |
| `/md/products/<slug>` | Plain-markdown variant of every product page | LLMs ingest copy without HTML noise — cited more reliably |
| `/journal/feed.xml` + `/journal/atom.xml` | RSS 2.0 + Atom 1.0 for the journal | Inktomi-style citation surface for AI summarisers + traditional feed readers |
| `/story/<slug>/` | Valid AMP `<amp-story>` doc per product (auto-built from images + book metafields) | Eligible for Google Discover carousel + Web Stories indexing |
| `/ai/products.json` | Paginated product feed with `numberOfItems` + `nextPage`; per-request cap 1000 | Direct ingestion endpoint for AI commerce agents |
| `/opensearch.xml` | Chrome tab-to-search registration | Lightweight discoverability win |
| `/.well-known/security.txt` | RFC 9116 contact/Expires/Policy | Security scanners stop flagging absence |
| `/.well-known/ucp.json` | Universal Commerce Protocol manifest | Discovered by Google + Shopify + Stripe + Etsy + Walmart |
| `/.well-known/agent.json` | Visa Trusted Agent + Mastercard Verifiable Intent acceptance | Identifies which AI agent placed which order |
| `/.well-known/indexnow-*.txt` | IndexNow verification keyfile | Powers same-second crawler push to Bing/Yandex/Naver/Seznam/Yep |
| `/manifest.webmanifest` + `/sw.js` | PWA manifest + service worker (cache-first static, network-first pages, offline fallback) | Storefront is installable + offline-capable |

All public SEO endpoints carry `Cache-Control: public, max-age=900, s-maxage=3600` and a best-effort `Last-Modified`. Crawlers stop re-running the full queryset on every hit.

### Structured data (JSON-LD) per page-type

| Page | Schemas emitted |
|---|---|
| Storefront base (every page) | `Organization`, `WebSite` with `SearchAction` |
| PDP | `Product` (+ `Book` subtype when `book.*` metafields exist) with `Offer`, `MerchantReturnPolicy`, configurable `shippingDetails` deliveryTime, gtin13, brand, sameAs · `AggregateRating` · individual `Review` nodes (up to 5) · `BreadcrumbList` · `SpeakableSpecification` · `FAQPage` + **`QAPage`** when FAQs exist · `ProductGroup` with `hasVariant` when the product has variants (preserves the Book signal too) |
| Category / Collection / Staff Picks | `CollectionPage` with `isPartOf`, `itemListOrder: ItemListOrderDescending`, correct `numberOfItems` (caller passes `total=`) |
| Journal entry | `Article` with `publisher` (reuses `organization_jsonld`), `mainEntityOfPage`, `image`, conditional `dateModified` (only when distinct from `datePublished`) |
| Vendor / author landing | `BreadcrumbList` |

### Automation

| Trigger | What fires |
|---|---|
| Product `post_save` (active) | IndexNow ping + WebStory rebuild + sitemap refresh signal |
| ProductImage `post_save` / `post_delete` | WebStory rebuild (cover swap reshuffles the story immediately) |
| Category `post_save` (active) | IndexNow ping via `CATEGORY_UPDATED` hook |
| Collection `post_save` | IndexNow ping via `collection.updated` |
| CMS Page published | IndexNow ping (gated on `state='published'` AND `is_live`) |
| Audit-run POST in dashboard | `messages.success` + redirect (no more raw JSON white-page) |

### Merchant dashboard surface

`/dashboard/seo/` is its own first-class IA, not a settings panel:

- **Overview** — outcome-ratio KPIs (`meta_complete_pct`, `not_found_7d` w/ delta, `keywords_in_top10`), one-click Ping IndexNow form, llms.txt freshness note
- **Sitemap** — per-type counts (Products / Categories / Collections / Vendors / Authors / Journal / Static / Manual), live URL table, IndexNow controls, sitemap-validate, manual `SitemapEntry` editor, truncation banner when over the cap
- **Audit** — per-product audit score with drill-down (View PDP / Edit / Bulk-meta filter), collapsible `<details>` for full issues + suggestions list
- **Bulk meta** — `?q=` search + `?missing=desc|title|both` filter + Paginator(50/page) + dynamic `maxlength` bound to `SiteSeoSettings` + inline char counters with warn/danger thresholds
- **404 log** — per-row Dismiss + Create redirect actions; sticky link to the new **Redirects manager** for full CRUD
- **Inspector** — paste a slug + type (product / category / collection / journal) and see the rendered head as a crawler does: title, description, canonical, robots, sitemap-presence, audit score, matching tracked keywords, JSON-LD, OG tags — all in one card
- **Keywords** — tracked keyword positions + delta over time
- **Settings** — `news_sitemap_max_age_hours`, sitemap caps, robots-meta defaults, shippingDetails handling/transit windows, per-bot allow/deny, **structured-data emission toggles** (Organization / WebSite / Product / Reviews)

### Web Stories at a glance

```
Product.images + book.* metafields
        │
        ▼ (post_save signal)
ensure_story(product)  ──── idempotent panel build
        │
        ├──→ panels = [cover, short_desc, …images, synopsis?, CTA]
        ▼
WebStory  (one row per product, OneToOne)
        │
        ├──→ /story/<slug>/           ←  valid <amp-story> doc (cache-headers + Last-Modified)
        ├──→ PDP <amp-story-player>   ←  StorefrontBlock(slot='pdp_above_long_description')
        ├──→ <link rel="amphtml">     ←  Google Discover hook
        └──→ /sitemap.xml             ←  Web Stories indexing
```

Backfill an existing catalog with `python manage.py backfill_webstories` (idempotent, `--dry-run` + `--limit` flags).

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

## Roadmap

A live snapshot of where we are and where we're going. Items move between tiers as they ship; this list is rebuilt with intent every couple of weeks. Anything marked **[done]** is already in `main`. (Recently shipped items have moved into [What's new](#whats-new-recent-waves).)

### Now (mid-2026)

| Track | Status | Notes |
|---|---|---|
| Robots-meta consolidation across cart/checkout/account/search (~19 templates) | in progress | Extend `seo_meta` with `noindex=True` flag → remove duplicated `<meta name="robots">` everywhere. Deferred from the SEO bundle because it exceeded the per-batch safety threshold. |
| Web Stories v2 — admin per-panel editor + theme overlay | queued | Reorder panels, edit captions / titles, set background overlay tint per merchant. v1 is auto-only. |
| Polling endpoint for Linda JSON mode (concurrency Phase 1) | queued | Async `/api/llm-tasks/` so the synchronous assistant path doesn't hold a gunicorn thread for 12 s LLM calls. |
| API stability contract for catalog/orders/cart GraphQL | queued | `docs/API_STABILITY.md` skeleton exists; we need versioned breaking-change cadence on the public surface. |

### Mid term (H2 2026)

| Track | Notes |
|---|---|
| **Headless-friendly REST/GraphQL completeness** | Move the operations that still live in Django views (search facets, account management, journal listing) into the public GraphQL schema. Saleor parity gap. |
| **Multi-warehouse stock reservation** | `inventory.allocator.plan_allocation` ships the cheapest-warehouse selector; the next step is per-warehouse reservations across split fulfillments with hard timeouts on hold expiry. |
| **Channel-specific pricing depth** | `ProductChannelListing` exists; we still need country-specific tax stacks + FX-aware refunds at multiple rate snapshots. |
| **Web Vitals p75 → SEO Audit feedback loop** | RUM already collects p75 per route; route them into the per-product SEO audit score so low-LCP PDPs surface in the dashboard. |
| **Background-agent visualisation timeline** | Per-agent timeline of runs / tokens / failures over a configurable window; tap into the run trace for the failing call. |
| **Marketplace payout automation** | Vendor onboarding + per-vendor order splitting is shipped; payouts go through draft `VendorPayout` rows. Wire to Stripe Connect / Wise. |

### Long term (2027 and beyond)

| Track | Notes |
|---|---|
| **Concurrency Phases 2 + 3** | Async-first GraphQL view, async-converted hot paths (`product_detail`, `cart_totals`), warm-pool of LLM provider connections. Lift per-container capacity from ~32 concurrent → ~250. |
| **Public-API stability tier** | Publish a versioned schema with a 6-month breaking-change deprecation window. The first published version waits for the headless-completeness gap above to close. |
| **Multi-store** (single deploy serves N storefronts) | `core.StoreChannel` already models the per-channel cut; routing host → channel + admin isolation per store is the missing piece. |
| **Enterprise compliance posture** | Third-party attestations on RBAC + audit log + data export — GDPR, PCI DSS SAQ-A, SOC 2 Type I as a starting set. |
| **Visual page builder for CMS Pages + Storefront Blocks** | A drag-and-drop block composer that targets the existing `cms.Page` + `StorefrontBlock` shape — no proprietary JSON format. |
| **Real-time agent presence on storefront** | Already foreshadowed by `core/channels.py`. Concierge agent can see who's on the site, what they're looking at, and proactively engage (with consent). |
| **Federated catalog (`morpheus://`) discovery** | Cross-store product search via the same MCP shape the platform already exposes for AI clients. |

### Architectural cleanup (in flight)

The **[2026 Architecture Audit](docs/plans/architecture-2026-audit.md)** identified three files that crossed the "needs splitting" threshold. Status:

| File | Before | Status |
|---|---|---|
| `plugins/installed/storefront/views.py` | 2098 LOC | **[done]** split into `home.py` / `catalog.py` / `cart.py` / `checkout.py` / `account.py` / `content.py` / `vendor.py` |
| `plugins/installed/seo/services.py` | 1907 LOC | **[done]** split into `services/sitemaps.py` / `crawler_files.py` / `jsonld.py` / `ai_feeds.py` / `feeds.py` / `_helpers.py` / `audit.py` etc. |
| `plugins/installed/admin_dashboard/forms.py` | 944 LOC | **[done]** decomposed into `forms/` package |
| `plugins/installed/catalog/services.py` | 896 LOC | queued — split per-entity (product / variant / category CRUD) |

The audit is rolling — re-run periodically against the current tree to spot new growth before it bakes in.

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

**Read in this order:**

1. [`CHARTER.md`](CHARTER.md) — **the project constitution.** Mission, audience, the 11 Laws (summary), layered architecture, governance, what Morpheus is and is NOT. When two docs disagree, this one wins.
2. [`RULES.md`](RULES.md) — the 11 immutable Laws expanded with rationale.
3. [`ARCHITECTURE.md`](ARCHITECTURE.md) — system design, plugin lifecycle, the four pillars.
4. [`SKILLS.md`](SKILLS.md) — named procedures for common tasks (add a plugin, fix N+1, deploy, …).
5. [`docs/PLUGIN_DEVELOPMENT.md`](docs/PLUGIN_DEVELOPMENT.md) — full plugin developer guide.
6. [`docs/THEME_DEVELOPMENT.md`](docs/THEME_DEVELOPMENT.md) — full theme developer guide.
7. [`AI_VISION.md`](AI_VISION.md) — the deep AI-first strategic thesis (intent engine, semantic search).

**Stability + ops:**

- [`docs/API_STABILITY.md`](docs/API_STABILITY.md) — public surface stability contract (what won't move within a major version)
- [`docs/PERFORMANCE.md`](docs/PERFORMANCE.md) — perf levers, baseline, regression-detection workflow
- [`docs/WEBHOOK_RECIPES.md`](docs/WEBHOOK_RECIPES.md) — Zapier / n8n / Make / curl recipes
- [`docs/HEADLESS.md`](docs/HEADLESS.md) — using Morpheus without the bundled theme
- [`docs/deploy-coolify.md`](docs/deploy-coolify.md) — Coolify deployment
- [`docs/deploy-plesk-nginx.md`](docs/deploy-plesk-nginx.md) — Plesk Nginx → Coolify Traefik proxy
- [`docs/OPERATIONS_RUNBOOK.md`](docs/OPERATIONS_RUNBOOK.md) — backups, restore, deploy chain, on-call
- [`CHANGELOG.md`](CHANGELOG.md) — every shipped PR by phase

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

- **3D bookstore walkthrough** — new [`bookstore_3d`](plugins/installed/bookstore_3d/) plugin. An immersive first-person 3D bookstore at `/walkthrough/`, rendered *inside* the active dot_books theme (header / nav / footer) with a full-bleed three.js canvas loaded from a CDN ES-module importmap — no build step. A pure plugin: disable it and the route is simply gone.
- **Lumina Book Creator landing** — new [`lumina`](plugins/installed/lumina/) plugin. A storefront landing page at `/create/` promoting "write a book with AI + voice", plus a "Write a book" link contributed into the theme's `nav_primary_extra` slot. Lives entirely in the plugin; disabling it removes both the page and the nav entry — a clean demonstration of the modularity contract.
- **Advanced payment gateways** — new [`advanced_payments`](plugins/installed/advanced_payments/) plugin. Two extra `PaymentGateway` adapters registered into the existing `GatewayRegistry`: a sandbox **test** gateway (always succeeds — for end-to-end checkout testing) and **cash on delivery** (`cod`). Shoppers can pick them at checkout; merchants disable the plugin to remove them.
- **Dynamic / personalized products** — new [`dynamic_products`](plugins/installed/dynamic_products/) plugin. Configurable `DynamicBlock` merchandising (for-you / related / recently-viewed) contributed into storefront slots (PDP, cart, home), coordinating with the `personalisation` plugin's frequently-bought-together block via slot priority.
- **Web Stories plugin** — new [`webstories`](plugins/installed/webstories/) plugin auto-generates a valid Google AMP `<amp-story>` document per product from images + book metafields, embeds an `<amp-story-player>` on the PDP, and exposes the story to Google via `<link rel="amphtml">` + sitemap inclusion. Auto-rebuilds on Product / ProductImage save. `python manage.py backfill_webstories` populates an existing catalog idempotently.
- **2026 SEO + AEO bundle (May 30, 2026 · `41df4cf`)** — a multi-dimensional audit found 31 verified improvements; **28 of 29 P0/P1/P2 items shipped in one commit** (+2311 / −420 across 21 files). Highlights: every storefront view now passes `seo_object` so the head-metadata pipeline actually runs; `robots.txt` advertises `/sitemap-index.xml`; every public SEO endpoint gained Cache-Control + Last-Modified; IndexNow now pings on Category / Collection / CMS-page edits, not just Product; **Book subtype JSON-LD** from `book.*` metafields; **individual `Review` nodes** alongside AggregateRating; **paste-a-slug SEO Inspector**; **404 redirects manager + Dismiss**; **`/.well-known/security.txt`** (RFC 9116); **RSS + Atom journal feeds**; **`seo_hreflang` templatetag** for multi-market stores; `/ai/products.json` paginated with `nextPage` + `numberOfItems`; bulk-meta with `?q=`/`?missing=`/Paginator + char counters; audit table drill-down; sitemap silently-truncated banner.
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

Apache 2.0 — see [LICENSE](LICENSE). Build whatever you want with it.

Morpheus is open-core: the platform you see in this repo is Apache 2.0.
Future enterprise plugins (advanced AI, multi-store, SSO/SCIM) may ship
under separate licensing in their own repos. Contributions to this repo
are always Apache 2.0 — see [CONTRIBUTING.md](CONTRIBUTING.md) and
[SECURITY.md](SECURITY.md).

<div align="center">
<sub>A modular ecommerce platform where every feature is a plugin — and AI agents are a first-class audience, not a chatbot tab.</sub>
</div>
