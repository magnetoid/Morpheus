# Morpheus — Project Charter

> **Status: canonical.** This document is the single authority for *what Morpheus is, who it's for, what's non-negotiable, and who decides*. Every other document (RULES.md, ARCHITECTURE.md, SKILLS.md, AI_VISION.md, docs/API_STABILITY.md) is the **how** for one slice of this charter. When two documents disagree, this one wins.

---

## 1. Mission

**Morpheus is the first open-source ecommerce platform with AI as a primary citizen — not an integration.**

Every model, hook, dashboard surface, and state transition is designed so an AI agent can use it before a human UI ever wraps it. The result: a self-hostable commerce engine that a single merchant can boot from one sentence, that a senior engineer can extend through a sharp plugin contract, and that an AI agent can operate end-to-end via the platform's own MCP server.

---

## 2. Primary audience

The Morpheus core is built **for the self-hosting merchant or technical agency** running:

- Catalogues of 50–50,000 SKUs
- $50k – $5M annual GMV
- One small dev team (1-5 engineers) or a single technical founder
- Choosing self-host over SaaS for cost, control, or compliance reasons
- Who explicitly wants AI-driven onboarding + ops, not bolted-on chatbots

This audience is **not** Shopify Plus enterprise merchants (Saleor wins there today); **not** five-shop dropshippers running Woo on $5 hosting; **not** "I just want a checkout SDK". It is the gap between Woo's plugin chaos and Saleor's headless-only steep ramp — and **AI-native** is the wedge nobody else fills.

Every architectural decision is judged against this audience. "Does this make life better for that merchant?" is the only acceptance test for new features in core.

---

## 3. Non-negotiables (the 11 Laws)

The platform laws live in [`RULES.md`](RULES.md). Summary:

| # | Law | Why it's non-negotiable |
|---|---|---|
| 0 | **Agentic First Touch** — every feature is designed for an AI agent before a human UI | The wedge of the whole project |
| 1 | **Everything Is a Plugin** — the core is just the engine | Without this, "modular" is marketing |
| 2 | **GraphQL First, Always** — the API is the product | Headless consumers and agents share one contract |
| 3 | **Storefront Never Touches the ORM** — storefront views call `internal_graphql()` | Keeps the API honest |
| 4 | **Plugins Communicate Via Hooks** — never via cross-plugin imports | Without this, the plugin promise breaks within a year |
| 5 | **Business Logic Lives in Services** — views and resolvers are thin | Testable + agent-callable |
| 6 | **Money Is Quantised at Every Step** — `Money` type, never raw floats | Production money bugs are unforgiving |
| 7 | **Every Write Goes Through Hooks** — `order.placed`, `product.updated`, … | Outbox + audit + agent observability all depend on this |
| 8 | **Agent Write Tools Take `confirmed: bool`** — irreversible operations require explicit consent | The platform won't let an LLM commit a refund alone |
| 9 | **Plugin Crashes Are Isolated** — broken `ready()` doesn't take siblings down | Foundation of the open-source extension story |
| 10 | **The Assistant Is Hard-coded in `core/`** — never a plugin | The "what just broke?" channel must always be reachable |

If a PR breaks any of these, it does not land — no matter who wrote it.

---

## 4. Layered architecture

```
┌──────────────────────────────────────────────────────────────┐
│  LAYER 5 — APPS         (community marketplace, future)       │
│   Installable, billable, can be turned off. Live in           │
│   docker-managed extra packages or a marketplace.             │
├──────────────────────────────────────────────────────────────┤
│  LAYER 4 — PLUGINS      (first-party, ship in the repo)       │
│   plugins/installed/<name>/. 49 today. Each: apps.py,         │
│   plugin.py, models.py, migrations/, tests/.                  │
├──────────────────────────────────────────────────────────────┤
│  LAYER 3 — THEMES       (storefront-only)                     │
│   themes/library/<name>/. Templates + CSS. Never imports      │
│   models. Communicates through StorefrontBlock contributions. │
├──────────────────────────────────────────────────────────────┤
│  LAYER 2 — MORPHEUS SDK (public Python surface)               │
│   `from morpheus import ...`. The contract third-party        │
│   plugins build on. Versioned. Backwards-compatible within    │
│   a major version.                                            │
├──────────────────────────────────────────────────────────────┤
│  LAYER 1 — CORE         (the engine)                          │
│   core/. Hooks, agents, audit, embeddings, money, i18n,       │
│   request_id, observability bootstrap, plugin registry,       │
│   theme loader, Morpheus Assistant. Tiny by design.           │
└──────────────────────────────────────────────────────────────┘
```

### The layer dependency rule (strict)

A layer may import from **lower** layers only. Never sideways. Never upward.

| From → | Core | SDK | Plugins | Themes | Apps |
|---|:---:|:---:|:---:|:---:|:---:|
| **Core** | ✓ | ✗ | ✗ | ✗ | ✗ |
| **SDK** | ✓ | ✓ | ✗ | ✗ | ✗ |
| **Plugins** | ✓ | ✓ | ✗* | ✗ | ✗ |
| **Themes** | ✗ | ✓ | ✗** | ✓ | ✗ |
| **Apps** | ✓ | ✓ | ✗* | ✗ | ✓ |

\* Cross-plugin communication happens via `core.hooks` + GraphQL. **Never** by direct Python import.
\** Themes consume the storefront blocks plugins contribute, never the plugins themselves.

---

## 5. The plugin contract

A plugin is a Python package under `plugins/installed/<name>/` that ships:

| File | Required? | Role |
|---|---|---|
| `__init__.py` | required | `default_app_config = 'plugins.installed.<name>.apps.<Name>Config'` |
| `apps.py` | required | Django `AppConfig` subclass with `name`, `label`, `default_auto_field` |
| `plugin.py` | required | `Plugin` subclass — name, label, version, requires, optional contributions |
| `models.py` | optional | Domain models. If present, must also have migrations. |
| `migrations/` | required if `models.py` | Generated by `manage.py makemigrations`. Hand-edits forbidden. |
| `urls.py` | optional | URL conf, mounted via `register_urls(prefix='dashboard/apps/<name>/')` |
| `views.py`, `services.py` | optional | Implementation. Business logic in services, never in views. |
| `graphql/` | optional | Strawberry extension. Schema additions must be backwards-compatible. |
| `templates/<name>/` | optional | Dashboard templates. Storefront templates go in `themes/`, not here. |
| `tests/` | required for any non-trivial plugin | `tests/` directory with pytest tests. PR bar in CONTRIBUTING.md. |

The `Plugin` subclass MAY contribute:

- `contribute_dashboard_pages()` → list of `DashboardPage`
- `contribute_storefront_blocks()` → list of `StorefrontBlock`
- `contribute_settings_panel()` → optional `SettingsPanel`
- `register_hook(event, handler, priority=N, mode='sync'|'async')` (within `ready()`)
- `register_urls(...)`, `register_graphql_extension(...)`

Anything else is breaking the contract and will be rejected.

---

## 6. Governance

### Today (Q2 2026)

**Benevolent Dictator (BDFL) model.** Marko Tiosavljevic ([@magnetoid](https://github.com/magnetoid)) is the sole maintainer with merge rights to `main`. All PRs route through him.

This is the right model while the codebase is finding its shape (months 0-18). It will not scale past ~3-5 active outside contributors.

### Phase 2 (planned, when 5+ outside contributors are active)

**Core team — 3-5 named humans.** A maintainer council with merge rights to `main`. Decisions:

- **Backwards-incompatible changes to LAYER 1 / LAYER 2 / the 11 Laws / this Charter:** require 2-of-N council approval + 14-day public RFC.
- **Backwards-compatible additions to LAYER 1 / LAYER 2:** any 1 council member can approve.
- **LAYER 3 (themes) / LAYER 4 (plugins):** any merge-rights contributor can approve.
- **Tie-breakers + emergencies:** BDFL retains final say.

### What stays BDFL-decided permanently

- The 11 Laws cannot be edited without a 6-month RFC + 4-of-5 council vote.
- The audience definition in section 2 of this charter cannot be edited without a 6-month RFC.
- Removing a feature from LAYER 1 requires 1-year deprecation + 4-of-5 council vote.

This is intentional. The platform's identity must be stable enough that someone investing 6 months building a plugin doesn't wake up to find the platform redirected.

---

## 7. What's stable, what isn't

Full surface map in [`docs/API_STABILITY.md`](docs/API_STABILITY.md). Summary:

| Surface | Stability |
|---|---|
| The 11 Laws (`RULES.md`) | Permanent. Editing requires 4-of-5 council vote. |
| The Plugin Contract (section 5 above) | Stable within a major version. Additions only. |
| `morpheus` Python SDK public API | Stable within a major version. |
| GraphQL `cartTotals`, `productDetail`, `checkoutComplete` | Stable. Frozen field set. |
| MCP server tool names + JSON-RPC shape | Stable. |
| Webhook event types + HMAC signing | Stable. |
| `/llms.txt`, `/md/products/<slug>` | Stable. Schema additions only. |
| Internal `plugins.installed.<x>.services.*` | **Not stable.** Cross-plugin imports go through `core.hooks`. |
| `/dashboard/*` URL paths | **Not stable.** Build dashboard customisations on plugin contribution APIs. |

Versioning: SemVer with the contract that "major" means a real, documented break in something the table above marks stable.

---

## 8. What Morpheus is NOT

Saying yes to one audience means saying no to others. Explicit non-goals:

- **NOT a hosted SaaS.** No `morpheus.com/signup` flow. Self-host first.
- **NOT a marketplace platform** in the eBay/Etsy sense (multi-vendor commerce IS a plugin — `marketplace/` — but two-sided-network mechanics aren't in core).
- **NOT a checkout SDK.** We ship a full storefront + admin; we don't compete with Stripe Checkout or Shop Pay as a drop-in widget.
- **NOT a CMS for blogging.** The `cms` plugin handles pages + journal posts because every store needs them; we're not chasing WordPress.
- **NOT a Magento replacement** for $500M+ GMV merchants in 2026. The architecture can scale there, but the feature set + ecosystem aren't there yet.
- **NOT a no-code platform.** We are opinionated about Python + Django. Visual editors are themes' responsibility, not core's.
- **NOT a Java/Spring/Phoenix port.** Python + Django + Strawberry GraphQL is the stack. Forever.

---

## 9. Contribution model

The PR bar lives in [`CONTRIBUTING.md`](CONTRIBUTING.md). Summary:

1. Read this charter, RULES.md, and the relevant SKILL in SKILLS.md before opening a PR.
2. New behaviour comes with tests. The whole suite must stay fast.
3. New features that aren't catalog → cart → checkout → fulfilment **must** be a plugin.
4. Don't add a top-level Django app for a new domain — make it a plugin.
5. Money paths require concurrency tests (the audit-deferred items are real bugs Saleor already has fixed).
6. Agent write tools take `confirmed: bool`. The platform refuses irreversible operations without explicit consent.
7. Plugin manifests must declare `requires` accurately. Crashes are isolated; broken dependencies should fail loud.
8. Major-version-breaking changes follow section 6 governance.

PRs that touch this charter file MUST be opened as an RFC with 14-day public comment.

---

## 10. Where to go next

Reading order for a new contributor:

1. **This file** (you are here).
2. [`RULES.md`](RULES.md) — the 11 immutable Laws, expanded.
3. [`ARCHITECTURE.md`](ARCHITECTURE.md) — the system design, plugin lifecycle, the 4 pillars.
4. [`docs/PLUGIN_DEVELOPMENT.md`](docs/PLUGIN_DEVELOPMENT.md) — how to write a plugin.
5. [`docs/THEME_DEVELOPMENT.md`](docs/THEME_DEVELOPMENT.md) — how to write a theme.
6. [`SKILLS.md`](SKILLS.md) — named procedures for common tasks (add a plugin, deploy, fix N+1, …).
7. [`docs/API_STABILITY.md`](docs/API_STABILITY.md) — the public-surface stability contract.
8. [`AI_VISION.md`](AI_VISION.md) — the deep AI-first design (intent engine, semantic search, agent layer).

For specific tasks:
- Performance work → [`docs/PERFORMANCE.md`](docs/PERFORMANCE.md)
- Webhook integration → [`docs/WEBHOOK_RECIPES.md`](docs/WEBHOOK_RECIPES.md)
- Headless storefront → [`docs/HEADLESS.md`](docs/HEADLESS.md)
- Deploy → [`docs/deploy-coolify.md`](docs/deploy-coolify.md)
- Operations → [`docs/OPERATIONS_RUNBOOK.md`](docs/OPERATIONS_RUNBOOK.md)

---

## 11. Amending this charter

Open an RFC at `docs/rfc/charter-<short-slug>.md` describing:

- The current text being changed
- The proposed text
- The rationale, including which audience the change serves
- The expected impact on existing plugins / themes / integrations

Public comment period: 14 days minimum. Approval bar:

- Section 2 (audience) or Section 8 (non-goals): 4-of-5 council + 30-day cool-down before merge
- Sections 5, 6, 7 (technical contracts): 2-of-N council + 14-day cool-down
- Everything else (formatting, links, examples, prose clarity): 1 council member can merge

The charter is the platform's spine. Editing it should feel heavy. It is.

---

*Last edited: this file is the authority. The git log of this file is the constitutional history of Morpheus.*
