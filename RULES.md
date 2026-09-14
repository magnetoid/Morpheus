# Morpheus Engine — Platform Rules

> **The law of the platform. Non-negotiable. Immutable.**
> Read this before writing a single line of code.

## The Mission
**Morpheus is the first commerce engine built natively for AI Agents.**
We do not treat AI as an API consumer or an afterthought. We treat AI agents as the **primary audience**. Every feature, endpoint, and capability must be fully understandable and executable by an LLM before a human UI is ever built.

Morpheus wins by being infinitely scalable, horizontally extensible via a rigorous plugin architecture, and completely free from legacy vendor lock-in. 

---

## The 11 Immutable Laws

### LAW 0 — Agentic First Touch ✦
**Every feature is designed for an AI agent to use it before a human ever sees it.**
- Can an agent call this via a single GraphQL operation?
- Is the response fully structured and machine-parseable?
- Does the GraphQL schema have `descriptions` on every type and argument? (This acts as the agent's prompt/documentation).
- Agents reach the store through the MCP servers in the `agent_mcp` app (`/mcp/*/v1/`) and the GraphQL schema; see `docs/MCP_SERVER.md`.

### LAW 1 — Everything Is a Plugin
**The core contains nothing but the engine. All commerce logic is a plugin.**
- The `core/` package only provides infrastructure: Hook registry, Plugin registry, Theme loader, Caching (`utils/cache.py`), and RBAC/Multi-tenancy models.
- Features (Products, Orders, Customers, AI) are completely decoupled into `plugins/installed/`.
- If a feature can be removed and the engine still boots, it must be a plugin.

### LAW 2 — GraphQL First, Always
**The API is the product. The UI is optional.**
- All mutations and queries must reside in the GraphQL schema.
- The storefront acts as a headless client consuming the GraphQL API via `api.client.internal_graphql()`.
- We support a REST API (`api/rest.py`), but it serves strictly as a versioned, read-only data layer for external aggregators.

### LAW 3 — The Storefront Never Touches the ORM
**Storefront views get all data from `internal_graphql()`. Zero exceptions.**
- The storefront is a living integration test of the API. Bypassing the API hides bugs.
- **Never** import models from `plugins/installed/*/models.py` inside a theme or storefront view.

### LAW 4 — Plugins Communicate Via Hooks & Outbox
**Plugins do not import from each other's internals. They use the hook registry.**
- Use `from core.hooks import hook_registry, MorpheusEvents`.
- Use `hook_registry.fire()` to trigger side-effects (e.g. `ORDER_PAID` triggers inventory reduction).
- Under the hood, `hook_registry.fire()` atomically writes to the `OutboxEvent` table. A Celery worker (`process_outbox`) reliably publishes these events to **NATS JetStream** to guarantee zero data loss.
- Remote Plugins (external Node/Go services) automatically receive these events via `WebhookEndpoint` or by directly subscribing to the NATS JetStream topics.

### LAW 5 — Business Logic Lives in Services
**Views receive HTTP. Resolvers receive GraphQL. Services do the work.**
- Place all business logic in `services.py` inside the respective plugin.
- Keep resolvers thin. Pass inputs to the service, and return the service's output.

### LAW 6 — Safe Money and Immutable States
**Currency is not a float. Order states are not arbitrary strings.**
- All money uses `MoneyField` from `djmoney`. Never use floats or raw decimals.
- Order statuses and transitions must use `django-fsm`. Direct mutation of state (e.g. `order.status = 'paid'`) is strictly forbidden. You must call state transitions (e.g. `order.confirm()`).
- All financial transitions generate an immutable `OrderEvent` for strict auditability.

### LAW 7 — All Primary Keys Are UUIDs
**No auto-increment integers as primary keys. Ever.**
- Prevent sequence prediction, ensure shard compatibility, and hide sales velocity.

### LAW 8 — All Stock Changes Are Atomic
**Never directly set `StockLevel.quantity`. Every change is audited.**
- Use atomic stock movement records with `select_for_update()` to prevent race conditions during high-concurrency checkouts.

### LAW 9 — All Caching is Event-Driven
**Aggressive caching requires smart invalidation.**
- We use Redis as our caching layer. 
- All GraphQL and REST read endpoints should be cached.
- Cache invalidation is bound to `MorpheusEvents` via `SmartCacheInvalidator`. (e.g. `PRODUCT_UPDATED` clears the product cache).

### LAW 10 — Multi-Tenancy and RBAC by Default
**Morpheus is built to serve Holding Companies and Headless architectures.**
- All top-level entities (Products, Orders) must map to a `StoreChannel` for multi-tenancy.
- API requests using Bearer tokens must be verified via `MorpheusAPIKeyAuthentication` to ensure agents and third-party tools do not exceed their authorized capabilities (`scopes`).

### LAW 11 — Observable by Design
**If it isn't traced and logged properly, it didn't happen.**
- Use the standard `logging` module. The `RequestIdFilter` injects `request_id` into every record automatically; in production logs come out as one-line JSON.
- OpenTelemetry injects `trace_id` and `span_id` when `OTEL_EXPORTER_OTLP_ENDPOINT` is set.
- Do not log raw PII or PCI data. Sentry's `before_send` already scrubs auth tokens, cookies, password / secret / token / card.
- Ensure all Celery tasks and database queries occur within an active trace + request_id context. Workers automatically inherit the request_id contextvar.
- Unhandled errors in DRF or GraphQL are masked and persisted to `ErrorEvent` (observability plugin) with the `request_id` — never let stack traces leak through API responses.

---

## Quick Reference Checklist for PRs

> Before writing code, scan [`SKILLS.md`](SKILLS.md) for the matching skill. If your change isn't covered by an existing skill, **add or update one in the same PR**.

Before merging any code, verify:
- [ ] Could an LLM agent execute this feature using only the GraphQL schema as documentation?
- [ ] Is business logic cleanly isolated in `services.py`?
- [ ] Are all state changes tracked via Event Sourcing or `django-fsm`?
- [ ] Are cross-plugin interactions handled via `hook_registry` rather than direct imports?
- [ ] Is the new model using a UUID primary key?
- [ ] Are all prices using `MoneyField`?
- [ ] Is the code accounting for Headless Multi-Tenancy (`StoreChannel`)?
- [ ] Tests pass and `manage.py makemigrations --check --dry-run` is clean.
- [ ] [`SKILLS.md`](SKILLS.md) reflects the new procedure (or the change is covered by an existing skill).
