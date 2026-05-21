# Morpheus — Architecture

> **This document is the source of truth for *how the platform is built*.**
> For *what Morpheus is and who decides*, see [`CHARTER.md`](CHARTER.md) — the canonical authority. For the immutable platform laws, see [`RULES.md`](RULES.md). For named procedures (add a plugin, deploy, fix N+1), see [`SKILLS.md`](SKILLS.md).
>
> **Status (2026-05-21):** v0.1 in production at [`dotbooks.store`](https://dotbooks.store). **49 plugins** active by default, dot_books theme, Morpheus Assistant hard-coded in core, agent kernel with Skills + background scheduling + observability dashboard, full commerce surface (Stripe + manual gateways · promotion engine v2 · draft orders · multi-warehouse allocator · RBAC · channels · i18n · audit log · gift cards · subscriptions · digital products) plus the agent-first surface (`/llms.txt`, agent GraphQL, MCP server, signed webhooks). Performance baseline (p95 ~250 ms median across storefront URLs) committed at [`docs/perf/baseline-prod-2026-05-21.jsonl`](docs/perf/baseline-prod-2026-05-21.jsonl).
>
> **Reading order:** [`CHARTER.md`](CHARTER.md) → [`RULES.md`](RULES.md) → this file → [`SKILLS.md`](SKILLS.md) → [`docs/PLUGIN_DEVELOPMENT.md`](docs/PLUGIN_DEVELOPMENT.md) → [`docs/THEME_DEVELOPMENT.md`](docs/THEME_DEVELOPMENT.md) → [`AI_VISION.md`](AI_VISION.md).
>
> **Deploy:** [`docs/deploy-coolify.md`](docs/deploy-coolify.md) · [`docs/deploy-plesk-nginx.md`](docs/deploy-plesk-nginx.md).
> **Stability surface:** [`docs/API_STABILITY.md`](docs/API_STABILITY.md).

---

## Layered architecture (canonical from `CHARTER.md` §4)

```
LAYER 5  APPS         (community marketplace, future)
LAYER 4  PLUGINS      (49 first-party today, `plugins/installed/<name>/`)
LAYER 3  THEMES       (storefront-only, `themes/library/<name>/`)
LAYER 2  MORPHEUS SDK (public Python API, `morpheus/`)
LAYER 1  CORE         (the engine, `core/`)
```

**The dependency rule (strict):** a layer may import from *lower* layers only. Never sideways. Never upward. Cross-plugin communication goes through `core.hooks` + GraphQL — *never* by direct Python import.

Detail in [`CHARTER.md` §4](CHARTER.md#4-layered-architecture). The rest of this document is the implementation — how the 4 pillars below realise the layered model.

---

## Vision

> **Morpheus is the first ecommerce platform designed for a world where AI agents shop, sell, and operate stores.**

Built for three kinds of users:
1. **Human merchants** — a more powerful CMS than Shopify/Magento/WooCommerce
2. **Human shoppers** — fast, personalized, beautiful storefront
3. **AI agents** — can autonomously browse, purchase, manage inventory, run storefronts

---

## The Fundamental Principle

> **The core contains the engine and the Assistant.**
> Almost every model, view, API type, and admin panel is a plugin —
> *except* the Morpheus Assistant, which is hard-coded in core so the
> merchant always has a window to ask "what just broke?" even when a
> plugin import explodes. Everything else (catalog, orders, even the
> agent kernel's specialised agents) is a plugin that ships enabled by
> default.

```
┌──────────────────────────────────────────────────────────────────────────┐
│                              MORPH CORE                                  │
│  Plugin Registry · Hook Registry · GraphQL Assembler · Theme Engine      │
│  Base Classes · Settings · Middleware · Celery · Outbox                  │
│  ┌──────────────────────────────────────────────────────────────────┐    │
│  │  core/assistant/  ← HARD-CODED MORPHEUS ASSISTANT (one)           │    │
│  │  - system tools (filesystem, DB, logs, plugins, system, delegate) │    │
│  │  - JSONL fallback persistence — usable when DB is down            │    │
│  │  - mounted at /admin/assistant/, never depends on plugin imports  │    │
│  └──────────────────────────────────────────────────────────────────┘    │
│  ┌──────────────────────────────────────────────────────────────────┐    │
│  │  core/agents/  ← AGENT KERNEL (programming surface for plugins)   │    │
│  │  - MorpheusAgent + Tool + Skill + AgentRuntime + LLMProvider      │    │
│  │  - skill_registry: reusable tool bundles agents opt into          │    │
│  └──────────────────────────────────────────────────────────────────┘    │
│  ┌──────────────────────────────────────────────────────────────────┐    │
│  │  core/audit/    core/i18n/   core/embeddings.py                   │    │
│  │  core/utils/{safe_db, rate_limit}     core/management/morph_backup │    │
│  └──────────────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────────────┘
                              │ loads & wires
         ┌────────────────────┼────────────────────┐
         ▼                    ▼                    ▼
  COMMERCE PLUGINS      AGENT PLUGINS         INFRA PLUGINS
  catalog · orders      agent_core            cloudflare
  customers · payments  ai_assistant          observability
  inventory · marketing ai_content            environments
  analytics · storefront functions            importers (+ CSV)
  tax · shipping        crm (Account Mgr)     seo
  wishlist · gift_cards advanced_ecommerce    webhooks_ui
  affiliates · b2b      admin_dashboard       demo_data
  marketplace · cms                           rbac
  subscriptions
  promotions · draft_orders
```

**Specialised agents** (shipped by `agent_core` and `crm`):
Concierge (storefront), Merchant Ops (admin), Pricing (system), Content
Writer (merchant), Account Manager (CRM merchant). The Assistant invokes
them via `delegate.invoke_agent`. **Background agents** can schedule any
of them on a fixed interval; `BackgroundAgent` rows are fired by Celery
beat and traced to the same `AgentRun` table as interactive runs.

---

## The 4 Pillars

### Pillar 1 — Plugin Native (Everything is a plugin)

**Rule:** If it can be removed and the engine still boots, it **must** be a plugin.

Plugins are self-contained Python packages in `plugins/installed/`. A plugin can contain:
- Django models + migrations
- GraphQL types, queries, mutations
- Django admin extensions
- Celery tasks
- Template tags / context processors
- Static assets
- Hook handlers
- URL routes

### Pillar 2 — GraphQL API First

**Rule:** Every feature must exist as a GraphQL operation before any UI exists for it.

One endpoint: `POST /graphql/`
Schema assembled dynamically at startup from all active plugins.

### Pillar 3 — Agent & AI First

**Rule:** AI agents are first-class participants — as shoppers, operators, and intelligence.

Dedicated agent auth, `agentCheckout` mutation, semantic search, LLM hooks on every major event.

### Pillar 4 — Theme System

**Rule:** Themes control only presentation. Zero business logic in themes.

Themes skin the storefront plugin. Swappable at runtime with zero downtime.

---

## Two-Tier Plugin Activation

This is the key architectural nuance. Plugins that define **Django models** must be known at startup (before the DB is connected), because Django needs to build the migration graph. Purely behavioral plugins can be toggled from the DB at runtime.

### Tier 1 — INSTALLED_APPS level (startup config)
Declared in `settings.py` via `MORPHEUS_DEFAULT_PLUGINS` and `MORPHEUS_EXTRA_PLUGINS` (from `.env`).
These plugins' models, migrations, and admin are always available.
Controls: **do the DB tables exist?**

### Tier 2 — Behavioral activation (DB toggle)
`PluginConfig` DB row per plugin. Toggled in the admin UI.
Controls: **are the plugin's URLs, hooks, GraphQL types, and tasks active?**

```
Plugin has models?
  YES → must be in INSTALLED_APPS (Tier 1). Can still be behaviorally disabled (Tier 2).
  NO  → only needs Tier 2 (DB toggle). No INSTALLED_APPS entry needed.
```

### Default Plugin Sets

**MORPHEUS_DEFAULT_PLUGINS** — always loaded, auto-enabled on first boot:
```python
MORPHEUS_DEFAULT_PLUGINS = [
    # ── Commerce core ────────────────────────────────────────────────
    'plugins.installed.catalog',       # Products, Variants, Categories, Collections, Vendors, Reviews
    'plugins.installed.orders',        # Cart, Order (FSM), Fulfillment, Refund, OrderEvent
    'plugins.installed.customers',     # Customer (AUTH_USER_MODEL), Addresses
    'plugins.installed.payments',      # Payment provider façade, Stripe webhooks
    'plugins.installed.inventory',     # Warehouses, StockLevel, StockMovement
    'plugins.installed.marketing',     # Coupons, campaigns, redirects
    'plugins.installed.analytics',     # Funnel events
    'plugins.installed.storefront',    # Theme-powered storefront (plugin!)
    'plugins.installed.admin_dashboard',# Merchant admin UI
    # ── AI & agent surface ──────────────────────────────────────────
    'plugins.installed.ai_assistant',  # Agent intents, signed receipts, semantic search, dynamic pricing
    'plugins.installed.ai_content',    # Generative product copy
    # ── Platform extensions ─────────────────────────────────────────
    'plugins.installed.functions',     # Sandboxed merchant-defined logic
    'plugins.installed.importers',     # Shopify, WooCommerce, … (idempotent)
    'plugins.installed.observability', # Per-merchant MerchantMetric rollups, ErrorEvent log
    'plugins.installed.environments',  # Dev/staging/prod with snapshots + promotion
    'plugins.installed.affiliates',    # Programs, links, attribution, payouts
    'plugins.installed.marketplace',   # Multivendor: vendor onboarding, order splitting, payouts
]
```

The plugin registry topologically sorts these by `requires` and activates them
in dependency order. Newly discovered plugins are auto-enabled on first boot
(see [`plugins/registry.py`](plugins/registry.py)).

**OPTIONAL — opt-in via `MORPHEUS_EXTRA_PLUGINS`:**
- `loyalty_points`, `wishlist`, `gift_cards`, `subscriptions`, `pos`, `b2b`

**Community plugins** — installed by merchants into `plugins/installed/`:
```python
# .env
MORPHEUS_EXTRA_PLUGINS=plugins.installed.my_custom_plugin,plugins.installed.another_one
```

---

## Plugin Anatomy

A full plugin with models looks like this:

```
plugins/installed/catalog/
├── plugin.py              ← MorpheusPlugin manifest (REQUIRED)
├── apps.py                ← Django AppConfig
├── models.py              ← Django models
├── migrations/            ← Django migrations
├── admin.py               ← Django admin registration
├── graphql/
│   ├── types.py           ← Strawberry type definitions
│   ├── queries.py         ← Query resolvers
│   └── mutations.py       ← Mutation resolvers
├── services.py            ← Business logic (no HTTP, no GraphQL)
├── hooks.py               ← Hook handlers (reacts to events from other plugins)
├── signals.py             ← Django signals
├── tasks.py               ← Celery tasks
├── urls.py                ← URL routes (if plugin has views)
├── views.py               ← Django views (if needed)
├── templates/             ← Templates (overridden by active theme)
├── static/                ← Static assets
└── tests/
    ├── test_models.py
    ├── test_graphql.py
    └── test_services.py
```

A **behavioral-only plugin** (no models) is simpler:
```
plugins/installed/analytics_gtm/
├── plugin.py
├── hooks.py               ← listens to order.placed, product.viewed etc.
└── tasks.py
```

---

## Plugin Base Class (`plugins/base.py`)

```python
class MorpheusPlugin:
    # ── Metadata ───────────────────────────────────────────────────
    name: str              # unique snake_case — matches directory name
    label: str             # human-readable
    version: str           # semver
    description: str
    author: str
    requires: list[str]    # plugin names this depends on
    conflicts: list[str]   # plugins this cannot coexist with
    has_models: bool = False  # True if plugin defines Django models

    # ── Lifecycle ──────────────────────────────────────────────────
    def ready(self):
        """Called when plugin is behaviorally activated. Register everything here."""
        pass

    def on_disable(self):
        """Called when plugin is deactivated."""
        pass

    # ── Registration helpers (call inside ready()) ─────────────────
    def register_urls(self, urlconf: str, prefix: str = ''): ...
    def register_graphql_extension(self, module: str): ...
    def register_hook(self, event: str, handler, priority: int = 50): ...
    def register_admin(self, model, admin_class): ...
    def register_celery_tasks(self, module: str): ...
    def register_context_processor(self, func): ...

    # ── Configuration ──────────────────────────────────────────────
    def get_config_schema(self) -> dict:
        """JSON Schema — rendered as settings UI in admin."""
        return {}

    def get_config(self) -> dict:
        """Read current config from PluginConfig DB row."""
        ...

    def set_config(self, key: str, value) -> None: ...
```

---

## Hook Registry & Transactional Outbox (`core/hooks.py`)

Morpheus relies on an immutable event-driven architecture. To guarantee zero data loss between the primary database and the event bus, we use the **Transactional Outbox Pattern**.

```
Event                        Fired by           Default listeners
─────────────────────────    ──────────────     ────────────────────────────────
order.placed                 orders             inventory (reserve), ai (upsell)
order.cancelled              orders             inventory (release), marketing
payment.captured             payments           orders (confirm), email receipt
payment.failed               payments           orders, email alert
cart.abandoned               orders (Celery)    marketing (recovery email), ai
product.viewed               storefront         analytics, ai (update model)
product.low_stock            inventory          analytics, notifications
product.out_of_stock         inventory          analytics, store alerts
customer.registered          customers          marketing (welcome email), ai
search.performed             storefront/api     analytics, ai (tune results)
ai.description_generated     ai_assistant       catalog (save to product)
```

Hook API:
```python
from core.hooks import hook_registry

# Register (in plugin.ready()):
hook_registry.register('order.placed', self.handle_order, priority=10)

# Fire (in service layer — never in views or GraphQL resolvers):
# This writes to the `OutboxEvent` table atomically with your DB transaction.
hook_registry.fire('order.placed', order=order)

# Filter (transform data through a chain):
price = hook_registry.filter('product.calculate_price', price=base_price, product=product)
```

### The Outbox Flow
1. **Mutation**: A domain service modifies state (e.g., creating an order).
2. **Hook**: The service calls `hook_registry.fire()`.
3. **Outbox Save**: The Hook Registry serializes the payload using `WebhookEncoder` and saves an `OutboxEvent` to the database *in the same transaction*.
4. **Publish**: A Celery worker (`process_outbox`) polls pending events and reliably publishes them to **NATS JetStream** (`morpheus_events` stream).
5. **Consumption**: Remote services and workers subscribe to NATS to execute side-effects.

---

## Observability & Log Aggregation

Morpheus provides enterprise-grade observability out of the box using OpenTelemetry.

- **Distributed Tracing**: Python's `logging`, Celery, Redis, and Psycopg2 are automatically instrumented. Every log line contains `trace_id` and `span_id`.
- **Log Aggregation**: Docker container logs are scraped by **Vector**, parsed as JSON, and shipped to **Grafana Loki**.
- **Metrics**: **Prometheus** scrapes metrics from the OpenTelemetry Collector and Celery workers.

---

## Autoscaling & GitOps

Morpheus is designed for horizontally scalable Kubernetes environments.
- **KEDA (Kubernetes Event-driven Autoscaling)**: The Celery workers are scaled dynamically based on the queue depth (lag) of the NATS JetStream `morpheus_events` topic.
- **Autonomous Ops Agent**: An AI-powered ops agent continuously monitors Prometheus metrics. If a scaling threshold is breached, the agent uses `PyGithub` to author a GitOps Pull Request against the `main` branch, modifying the `replicas` count in the Kubernetes manifests.

---

## GraphQL Schema Assembly (`api/schema.py`)

```python
import strawberry
from plugins.registry import plugin_registry

def build_schema():
    query_bases = [CoreQuery] + plugin_registry.get_graphql_extensions('query')
    mutation_bases = [CoreMutation] + plugin_registry.get_graphql_extensions('mutation')

    @strawberry.type
    class Query(*query_bases): pass

    @strawberry.type
    class Mutation(*mutation_bases): pass

    return strawberry.Schema(
        query=Query,
        mutation=Mutation,
        extensions=[QueryDepthLimiter, AgentContextExtension],
    )

schema = build_schema()
```

---

## Directory Structure (Final)

```
morph/
│
├── morph/                           # Django project config ONLY
│   ├── settings.py                  # Loads plugins into INSTALLED_APPS
│   ├── urls.py                      # Only: /graphql/, /admin/, plugin aggregator
│   ├── celery.py
│   ├── wsgi.py
│   └── asgi.py
│
├── core/                            # ★ ENGINE ONLY — no business logic
│   ├── hooks.py                     # HookRegistry
│   ├── models.py                    # StoreSettings ONLY (needed at engine level)
│   ├── context_processors.py
│   ├── middleware.py
│   └── admin.py                     # Morph admin site config
│
├── api/                             # ★ GraphQL layer — assembles from plugins
│   ├── schema.py                    # Dynamic schema assembly
│   ├── urls.py                      # /graphql/ + /graphql/agent/
│   ├── client.py                    # Internal GraphQL client
│   └── permissions.py
│
├── plugins/                         # ★ PLUGIN ENGINE
│   ├── base.py                      # MorpheusPlugin base class
│   ├── registry.py                  # Discovery, lifecycle, activation
│   ├── middleware.py                # Inject active plugin URLs per request
│   ├── context_processors.py
│   └── installed/                   # ← EVERYTHING LIVES HERE
│       │
│       ├── catalog/                 # DEFAULT ✓ — Products, Categories, Variants
│       │   ├── plugin.py
│       │   ├── models.py
│       │   ├── migrations/
│       │   ├── graphql/
│       │   ├── services.py
│       │   ├── admin.py
│       │   └── ...
│       │
│       ├── orders/                  # DEFAULT ✓ — Cart, Order, Fulfillment
│       │   └── ...
│       │
│       ├── customers/               # DEFAULT ✓ — Customer (AUTH_USER_MODEL)
│       │   └── ...
│       │
│       ├── payments/                # DEFAULT ✓ — Stripe, multi-gateway
│       │   └── ...
│       │
│       ├── inventory/               # DEFAULT ✓ — Warehouses, Stock
│       │   └── ...
│       │
│       ├── marketing/               # DEFAULT ✓ — Coupons, Campaigns
│       │   └── ...
│       │
│       ├── analytics/               # DEFAULT ✓ — Events, Funnels
│       │   └── ...
│       │
│       ├── storefront/              # DEFAULT ✓ — Theme-powered frontend
│       │   ├── plugin.py
│       │   ├── views.py             # Queries own GraphQL API — never ORM directly
│       │   ├── urls.py
│       │   ├── templates/           # Overridden by active theme
│       │   └── static/
│       │
│       ├── ai_assistant/            # DEFAULT ✓ — LLM, semantic search, agents
│       │   ├── plugin.py
│       │   ├── models.py            # AIInteraction log, AIPromptTemplate
│       │   ├── services/
│       │   │   ├── llm.py           # Swappable LLM gateway
│       │   │   ├── embeddings.py
│       │   │   ├── rag.py
│       │   │   └── recommendations.py
│       │   ├── graphql/
│       │   │   ├── types.py         # AgentCapabilities, AIResponse, etc.
│       │   │   ├── queries.py       # recommendations, semanticSearch, chatMessage
│       │   │   └── mutations.py     # agentCheckout, generateDescription, optimizePrice
│       │   └── tasks.py
│       │
│       ├── reviews/                 # OPTIONAL ○ — Product reviews & ratings
│       ├── wishlist/                # OPTIONAL ○
│       ├── loyalty_points/          # OPTIONAL ○
│       ├── gift_cards/              # OPTIONAL ○
│       ├── subscriptions/           # OPTIONAL ○
│       ├── pos/                     # OPTIONAL ○
│       ├── multi_vendor/            # OPTIONAL ○
│       └── b2b/                     # OPTIONAL ○
│
├── themes/                          # ★ THEME ENGINE
│   ├── base.py                      # MorpheusTheme base class
│   ├── registry.py
│   ├── middleware.py                # Set active theme per request
│   ├── loaders.py                   # Theme-aware Django template loader
│   ├── models.py                    # ThemeConfig
│   └── library/                     # ← THEMES LIVE HERE
│       └── aurora/                  # Built-in default theme
│           ├── theme.py
│           ├── templates/
│           ├── static/
│           └── config_schema.json
│
├── templates/                       # Global fallback templates only
├── static/                          # Global static only
├── media/
├── ARCHITECTURE.md
├── requirements.txt
└── .env.example
```

---

## Storefront Plugin — GraphQL-First Pattern

The storefront plugin **never imports from other plugin models directly**. It only talks to the GraphQL API via an internal client. This is enforced by convention and linting.

```python
# plugins/installed/storefront/views.py
from api.client import internal_graphql   # ← ONLY allowed data access

def product_list(request):
    result = internal_graphql("""
        query ProductList($first: Int!, $category: String) {
          products(first: $first, category: $category) {
            edges { node { id name slug price { amount currency } primaryImage { url } } }
          }
        }
    """, variables={"first": 24, "category": request.GET.get('cat')}, request=request)
    return render(request, 'storefront/product_list.html', result)
```

This means: **the storefront is a living integration test of the GraphQL API**.

---

## AI Agent Flow

```
AI Agent → POST /graphql/agent/
  Authorization: AgentToken abc123

  → AgentAuthMiddleware: verify, load AgentCapabilities (budget, categories, permissions)
  → mutation agentCheckout(items: [...]) {
      → validate items within agent budget & allowed categories
      → reuse same CartService, OrderService as human checkout
      → return { order { orderNumber total } receipt { lineItems tax shipping } }
    }
```

Agents are rate-limited separately from humans and have explicit capability scopes (read-only, purchase-allowed, inventory-manage).

---

## Implementation Checklist (Phase 1)

### Engine (core + api + plugins engine + themes engine)
- [x] Django project scaffold
- [x] Supabase PostgreSQL with SSL
- [ ] `core/hooks.py` — HookRegistry
- [ ] `core/models.py` — StoreSettings only
- [ ] `plugins/base.py` — MorpheusPlugin base class
- [ ] `plugins/registry.py` — discovery, two-tier activation
- [ ] `plugins/middleware.py`
- [ ] `themes/base.py` — MorpheusTheme base class
- [ ] `themes/registry.py` + `themes/loaders.py`
- [ ] `api/schema.py` — dynamic schema assembly
- [ ] `api/client.py` — internal GraphQL client
- [ ] `morph/settings.py` — load plugins into INSTALLED_APPS dynamically

### Default Plugins — Models
- [x] `catalog` models (moved → `plugins/installed/catalog/models.py`)
- [x] `orders` models (→ `plugins/installed/orders/models.py`)
- [x] `customers` models (→ `plugins/installed/customers/models.py`)
- [x] `payments` models (→ `plugins/installed/payments/models.py`)
- [x] `inventory` models (→ `plugins/installed/inventory/models.py`)
- [x] `marketing` models (→ `plugins/installed/marketing/models.py`)
- [ ] All models need plugin.py manifests + apps.py + migrations
- [ ] `ai_assistant` — AIInteraction, AIPromptTemplate models

### Default Plugins — GraphQL
- [ ] `catalog` — types, queries (products, product, categories, search)
- [ ] `orders` — types, mutations (addToCart, checkout, createOrder)
- [ ] `customers` — types, mutations (register, login, updateProfile)
- [ ] `ai_assistant` — types, queries (semanticSearch, recommendations, chatMessage)
- [ ] `ai_assistant` — mutations (agentCheckout, generateDescription)

### Default Plugins — Storefront
- [ ] `storefront/plugin.py`
- [ ] `storefront/views.py` (GraphQL-consuming)
- [ ] `themes/library/aurora/` — first theme

### Final
- [ ] All migrations
- [ ] Django admin customisation
- [ ] Working `/graphql/` explorer (GraphiQL)
- [ ] `manage.py runserver` green

---

## Rules for Contributors

1. **GraphQL first** — API operation before UI
2. **Service layer for logic** — business logic in `services.py`, never in views/resolvers
3. **Hooks for cross-plugin events** — never import between plugins directly
4. **No ORM in storefront views** — data from `internal_graphql()` only
5. **No logic in themes** — themes are HTML/CSS/JS only
6. **All money = MoneyField** — never FloatField or raw DecimalField
7. **All PKs = UUID** — no auto-increment integers
8. **All stock changes via StockMovement.record()** — never raw `.save()`
9. **All AI calls logged to AIInteraction** — always
10. **Models live inside their plugin** — never in a standalone Django app
