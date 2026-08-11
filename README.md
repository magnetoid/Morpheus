<div align="center">

# Morpheus OS

### The AI-native commerce platform you **own** — and can **talk to**.

*Describe your shop in a sentence → a real store in ~20 seconds. Toggle any of 100+ features like apps. Hand the back office to an AI operator who learns your store, briefs you each morning, and proposes her own upgrades — every code change reviewed by a panel of independent LLMs and then by you.*

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Live store](https://img.shields.io/badge/live-dotbooks.store-ff5722.svg)](https://dotbooks.store)
[![Self-host](https://img.shields.io/badge/self--host-no%20platform%20fees-16a34a.svg)](#-quick-start)
[![Plugins](https://img.shields.io/badge/plugins-108%20toggleable-2563eb.svg)](#-everything-is-a-plugin)
[![AI operator](https://img.shields.io/badge/AI-built--in%20operator%20(Linda)-e11d48.svg)](#-meet-linda--the-ai-operator)
[![Agentic](https://img.shields.io/badge/agentic-MCP%20%2F%20ACP%20%2F%20UCP-7c3aed.svg)](#-agentic-commerce-be-transactable-by-ai)
[![Stack](https://img.shields.io/badge/django%206-postgres%20%C2%B7%20celery%20%C2%B7%20graphql-092e20.svg)](#-tech-stack)

**[▶ See it live](https://dotbooks.store)  ·  [🚀 Run your own](#-quick-start)  ·  [🧠 Architecture](#-architecture-a-tiny-kernel-a-big-ecosystem)  ·  [🤖 Agentic surface](#-agentic-commerce-be-transactable-by-ai)  ·  [📚 Docs](#-documentation)**

</div>

---

## What is Morpheus?

**Morpheus is a self-hosted, Shopify-grade commerce engine built for the agentic web.** Three convictions set it apart from every other open-source store:

1. **AI is a built-in co-worker, not a monthly add-on.** A single AI operator — *Linda* — runs on your infrastructure, learns your catalog and customers, executes real back-office work through a governed tool surface, and even proposes improvements to her own codebase. Every AI action is scoped, approvable, staged, budget-capped, and audited.
2. **Everything is a plugin — and disabling one leaves no trace.** The kernel is a small set of extension points. All 108 shipped features — catalog, checkout, loyalty, 3D storefronts, ad channels, B2B — live in `plugins/installed/<name>/` and contribute their surfaces through hooks and contribution APIs. Toggle a plugin off and *every* nav entry, settings page, storefront block, and route it added vanishes.
3. **You are maximally legible and transactable to AI — never intermediated.** Morpheus ships a real MCP server, an Agentic Commerce Protocol (ACP) checkout, a Universal Commerce Protocol (UCP) manifest, `llms.txt`/`agents.md`, and native trusted-agent verification. Shoppers discover you inside ChatGPT/Gemini/Perplexity and convert on **your** storefront — you stay Merchant-of-Record.

> **The harness is the product.** Lots of platforms will bolt on an LLM. Morpheus's moat is the *safety and governance layer* around AI — approvals, staged writes, merchant guardrails, an immune-system self-improvement loop, and an EU AI Act evidence trail — that makes handing real authority to an agent safe.

---

## Table of contents

- [Why Morpheus](#-why-morpheus)
- [Meet Linda — the AI operator](#-meet-linda--the-ai-operator)
- [Agentic commerce: be transactable by AI](#-agentic-commerce-be-transactable-by-ai)
- [Architecture: a tiny kernel, a big ecosystem](#-architecture-a-tiny-kernel-a-big-ecosystem)
- [Everything is a plugin](#-everything-is-a-plugin)
- [The self-improvement loop](#-the-self-improvement-loop)
- [Safety, security & compliance](#-safety-security--compliance)
- [Tech stack](#-tech-stack)
- [Quick start](#-quick-start)
- [Project structure](#-project-structure)
- [Development workflow](#-development-workflow)
- [Deployment](#-deployment)
- [Documentation](#-documentation)
- [License](#-license)

---

## ✨ Why Morpheus

| | Morpheus | Hosted SaaS (Shopify/BigCommerce) | Other open-source (Woo/Medusa/Saleor) |
|---|---|---|---|
| **AI operator** | Built-in, governed, on *your* infra | Add-on / per-seat copilot | DIY |
| **Agent-transactable** | MCP + ACP + UCP + Web Bot Auth, native | Emerging, platform-mediated | Rare |
| **Feature model** | 108 plugins, disable-safe by construction | Apps (billed, sandboxed) | Extensions/modules |
| **Own your data & code** | Yes — self-hosted, Apache-2.0 | No | Yes |
| **Platform fees** | None | % of revenue + app fees | None |
| **Self-improving** | LLM-panel-reviewed code changes | — | — |
| **EU AI Act ready** | Art. 50 disclosure + evidence export | Varies | DIY |

**Who it's for:** merchants who want Shopify-grade capability without the platform tax; teams that want an AI staff member with real guardrails; and builders positioning for a web where a growing share of shopping is agent-orchestrated.

---

## 🧠 Meet Linda — the AI operator

Morpheus has **one generalist AI worker**, not a zoo of specialist bots. Linda is the conversational operator; the **Worker** is the same runtime executing autonomous or delegated jobs. Specialization comes from *skills* (curated tool bundles) and *scopes*, never from new agent classes.

What she does, safely:

- **Runs the store from a command bar** — "mark order #1042 refunded", "find low-stock hardcovers", "draft the October newsletter". Reads and writes flow through a typed tool registry.
- **Briefs you** — a morning digest of what changed and what needs attention (the Brain aggregator).
- **Proposes upgrades to her own code** — improvements are generated, then **judged by a panel of independent LLMs**, then queued for **your** approval. No machine merges alone.

The governance that makes this safe (all enforced in `core/`, read from one place):

- **Scopes** — every tool declares required scopes; a caller only sees tools it may call.
- **Human approval** — high-risk writes create a **server-side, fingerprint-bound, single-use approval record** and *fail closed* if the approver backend is unavailable.
- **Staged writes** — an agent can record an `OpsProposal` for human review instead of executing (`DIRECT` vs `STAGED`).
- **Merchant guardrails** — a kill switch, daily run/spend caps, and per-action price/refund ceilings, read cross-process-fresh from the *Agent guardrails* settings panel.
- **Budgets, deadlines, compaction, tracing** — one execution kernel owns them.
- **Audit** — every executed tool call and every denial writes an `AgentRun`/decision row (the EU AI Act evidence substrate).

See [`docs/SKILLS.md`](docs/SKILLS.md) and [`AI_VISION.md`](AI_VISION.md).

---

## 🤖 Agentic commerce: be transactable by AI

Morpheus is designed so an external agent (Claude, ChatGPT, Gemini, Perplexity) can **discover, browse, cart, and check out** — while the merchant keeps the conversion surface and stays Merchant-of-Record.

- **MCP server** — a real JSON-RPC 2.0 Model Context Protocol surface with audience-scoped clusters:
  - `POST /mcp/storefront/v1/` — catalog reads
  - `POST /mcp/cart/v1/` — cart build
  - `POST /mcp/checkout/v1/` — checkout build + quote *(the charge stays off MCP by design)*
  - `POST /mcp/admin/v1/` — the operator's admin tool catalog (Bearer + scopes)
  - Discovery (`initialize`, `tools/list`) is anonymous; **executing** any tool requires a Bearer token, per-token scopes, rate limits, a per-token approval grant for protected writes, and an audit row.
- **ACP checkout** (`/acp/…`) — a conformant Agentic Commerce Protocol checkout session (multi-item carts, live tax/shipping quotes, quote-drift refusal before charge, idempotent completion under a row lock). Completion is gated behind `payments_enabled` and reuses the canonical order/money path — **one implementation**, zero duplicated totals logic between MCP and ACP.
- **UCP manifest** (`/.well-known/ucp.json`) — capabilities computed **live** from what's actually registered and enabled, never hardcoded.
- **Trusted agents** — Visa Trusted Agent / Mastercard Verifiable Intent / Cloudflare Web Bot Auth headers, honored only from a verified proxy origin (fail-closed by default).
- **GEO / answer-engine readiness** — `llms.txt`, `agents.md`, schema-dense JSON-LD, and a merchant Q&A knowledge layer so AI answer engines can read and recommend your store.

Deep dive: [`docs/MCP_SERVER.md`](docs/MCP_SERVER.md) · [`docs/AGENT_PROTOCOLS.md`](docs/AGENT_PROTOCOLS.md) · [`docs/MORPHEUS_API.md`](docs/MORPHEUS_API.md).

---

## 🏗️ Architecture: a tiny kernel, a big ecosystem

**Powerful *through* modularity, not by bloating core.** The kernel is the mechanism that keeps a deep commerce engine swap-able, disable-safe, and agent-legible.

```
                         ┌────────────────────────────────────────┐
   Shoppers · Staff ·    │            Entry surfaces               │
   AI agents · Webhooks  │  Storefront · Dashboard · GraphQL ·     │
        │                │  REST · MCP · ACP · Assistant · Tasks   │
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
        catalog        orders      payments     agent_mcp   …104 more plugins
        (a plugin)    (a plugin)  (a plugin)   (a plugin)   in plugins/installed/
```

**What lives in `core/`:** only what's foundational — auth, the hooks/event bus, settings, request lifecycle, i18n kernel, observability, the **agent runtime** (persists `AgentRun`/`AgentStep`/approvals), the **safety boundary** (`core/safety.py` — the single source of truth for what AI may touch), and the **self-improvement loop**. Nothing else. A CI **core-boundary ratchet** (`scripts/check_core_boundary.py`) enforces that `core/` imports **zero** plugins — the count is pinned at 0.

**What lives in a plugin:** everything else — models, migrations, views, URLs, templates, dashboard pages, settings panels, GraphQL, tasks. A plugin appears *elsewhere* only by **contributing**, never by editing another layer:

- Storefront surface → a `StorefrontBlock(slot=…)`
- Dashboard page / nav / settings → a dashboard-page / nav / settings-panel contribution
- Behavior in another plugin's flow → a `core.hooks` subscriber (never a cross-plugin model import)

**Two litmus tests every feature passes:** *delete* the plugin folder → the feature is gone with no dangling reference; *disable* the plugin → every surface it added disappears from the OS.

**Three SDK doors** curate the common imports (ADR 0035):

| Door | For | Exposes |
|---|---|---|
| `morpheus.app` | plugin authors | `Plugin`, `StorefrontBlock`, `DashboardPage`, `SettingsPanel`, `.views/.models/.forms` |
| `morpheus.core` | cross-cutting | `events`, `hooks`, `tool`, `ToolResult`, `record_ai_decision`, `Money`, … |
| `morpheus.theme` | theme authors | storefront slot contract |

More: [`ARCHITECTURE.md`](ARCHITECTURE.md) · [`docs/PLUGIN_DEVELOPMENT.md`](docs/PLUGIN_DEVELOPMENT.md) · [`CHARTER.md`](CHARTER.md).

---

## 🧩 Everything is a plugin

All **108** shipped capabilities are toggleable plugins (source of truth: `MORPHEUS_DEFAULT_APPS` in `morph/settings.py`). A sampling by domain:

- **Core commerce** — `catalog` · `orders` · `inventory` · `payments` · `shipping` · `tax` · `checkout_experience` · `draft_orders` · `customers` · `one_click` · `smart_shipping` · `advanced_payments`
- **Merchandising & pricing** — `promotions` · `gift_cards` · `loyalty_points` · `subscriptions` · `drops` · `bundles`-style flows · `markets` · `metafields`
- **AI & agents** — `agent_core` · `agent_mcp` · `agentic_checkout` · `ai_assistant` · `ai_content` · `ai_stylist` · `morpheus_brain` · `discovery_quiz` · `personalisation` · `lumina`
- **Storefront & immersive** — `storefront` · `cms` · `richtext` · `media` · `media_3d` · `bookstore_3d` · `immersive_pdp` · `flipbook` · `lookbook` · `product_stories` · `product_videos` · `webstories` · `live_commerce` · `pwa`
- **Growth & retention** — `marketing` · `seo` · `newsletter` · `referrals` · `affiliates` · `reviews` · `ugc_reviews` · `trust_signals` · `cart_abandonment` · `post_purchase` · `post_checkout_upsell` · `save_for_later` · `wishlist` · `experiments`
- **Channels & marketplaces** — `google_shopping` · `meta_commerce` · `tiktok_commerce` · `pinterest_commerce` · `microsoft_commerce` · `snapchat_commerce` · `reddit_ads` · `amazon_ads` · `channels` · `marketplace`
- **B2B & internationalization** — `b2b` · `markets` · `localization`
- **Ops, security & compliance** — `admin_dashboard` · `rbac` · `staff_mfa` · `staff_sso` · `gdpr` · `consent` · `fraud_rules` · `observability` · `backups` · `webhooks_ui` · `notifications_center` · `analytics` · `workflows` · `cloudflare`
- **Verticals** — `book_product` · `bookvault` · `audiobooks` · `booking_marketplace` · `digital_products` · `eco_impact`

> **Before adding a plugin:** audit for overlap and justify the boundary — *one concept, one owner*. A sibling ratchet (`scripts/check_plugin_boundary.py`) keeps plugins from importing each other except through declared `requires` + hooks.

---

## ♻️ The self-improvement loop

The "immune system" of a vibecoded platform — and the one thing that *cannot* be a togglable plugin, so it lives in `core/`:

- **Autonomic engine** — Linda proposes code and content improvements.
- **Code-quality scanner** — catches regressions and drift.
- **Upstream-drift tracking** — watches dependencies.
- **LLM consensus review** — a panel of independent models judges each proposed change before it ever reaches a human.
- **Human gate** — you approve. Machines never merge alone.

Paired with **hooks as the enforcement layer** (PostToolUse hooks run `ruff`/`mypy`/forbidden-import checks on every AI edit) and a CI suite that blocks broken migrations against real Postgres.

---

## 🔒 Safety, security & compliance

- **Safety boundary** — `core/safety.py` is the single source of truth for what AI may touch; read by the self-improvement loop, `agent_mcp`, CI hooks, and pre-commit.
- **Staff MFA & SSO** — second-factor and SSO ship as plugins; a landmine guard ensures no new sign-in path bypasses MFA.
- **RBAC** — role scopes for staff and per-token scopes for agents.
- **GDPR & consent** — data-subject flows and consent-gated analytics.
- **EU AI Act** — Article 50 chatbot/synthetic-content disclosure, plus a dated **evidence export** (decision + approval trail) from `record_ai_decision`.
- **Supply chain** — hash-pinned `requirements.lock.txt` (uv), `pip-audit` enforced in CI, bandit, dependabot.

See [`SECURITY.md`](SECURITY.md) · [`docs/COMPLIANCE.md`](docs/COMPLIANCE.md).

---

## 🛠 Tech stack

- **Django 6** (Python 3.12) · **PostgreSQL** · **Redis** · **Celery** (+ beat)
- **Strawberry GraphQL** (stable public API) + **DRF** for REST
- **djmoney** for multi-currency money · **allauth** for auth/SSO
- **MCP / ACP / UCP** agent protocols · **Web Bot Auth** trusted agents
- Self-hosted behind **Cloudflare → Plesk → Coolify (Traefik)**; container-first (`Dockerfile`, `docker-compose.yml`)

---

## 🚀 Quick start

### Option A — Docker (full stack: Postgres + Redis + worker + beat)

```bash
git clone https://github.com/magnetoid/morpheus.git
cd morpheus
docker compose up -d
```

The `web` service auto-migrates on boot. Open **http://localhost:8000/dashboard/** — the first signup becomes the owner. Then bootstrap a store from one sentence at **/dashboard/start/**.

### Option B — No Docker (SQLite, sync paths only)

```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

> Async (`.delay()`) work needs Redis/Celery, so the plain `runserver` path covers request/response but not background jobs — use the compose stack for the full experience. Details in [`docs/QUICK_START.md`](docs/QUICK_START.md).

### Run the tests

```bash
# Always pin an in-memory DB — a bare `manage.py test` tries the Docker `db` host.
DATABASE_URL='sqlite:///:memory:' python manage.py test plugins.installed.<name>
```

---

## 📁 Project structure

```
morph/
├── core/                      # the kernel: auth, hooks, agents runtime, safety, self-improvement
│   ├── agents/                # agent runtime, tool registry, guardrails, approvals
│   ├── assistant/             # Linda's conversational runtime
│   ├── hooks.py               # the fire/filter event bus (plugin coupling goes here)
│   └── safety.py              # single source of truth for what AI may touch
├── morph/                     # Django project: settings, root urls, MORPHEUS_DEFAULT_APPS
├── morpheus/                  # the three SDK doors: {plugin, core, theme}
├── plugins/installed/<name>/  # all 108 features — apps.py, app.py, models, migrations, templates
├── themes/                    # storefront themes (contribution-driven; e.g. dot_books)
├── api/                       # GraphQL view + hardening
├── scripts/                   # CI ratchets (core-boundary, plugin-boundary, api-stability, release)
├── docs/                      # architecture, plugin dev, MCP, API, compliance, runbooks, …
└── docker-compose.yml         # full local stack
```

---

## 🧭 Development workflow

Morpheus is built for AI-assisted development with hard guardrails. The house rules that keep it coherent live in [`CLAUDE.md`](CLAUDE.md) (Claude-specific) and [`AGENTS.md`](AGENTS.md) (cross-IDE). Highlights:

- **One concept = one owner.** Extend another plugin via FK/OneToOne + hooks, never a parallel table.
- **Add a migration before merge** (system check fails on a model without one; CI applies every migration against real Postgres).
- **Ship code and docs together.** A change to architecture, a convention, or a public contract updates the matching Markdown in the same commit.
- **Every deploy bumps the version.** Run `python manage.py release --minor "Headline" -m "bullet"` — it updates `MORPHEUS_VERSION` and prepends a dated [`docs/RELEASE_NOTES.md`](docs/RELEASE_NOTES.md) entry atomically. `release --check` is a blocking CI gate.
- **Verify for real.** A green type/lint/syntax check is necessary, not sufficient — smoke the actual behavior.

---

## 🗂️ Project memory: torsor-helper

Morpheus is built with heavy AI assistance, so it carries a **durable, retrievable project brain** that survives across sessions and keeps architectural decisions from being re-litigated. That brain is **torsor-helper** (adopted in ADR 0001), and it lives under [`.torsor/`](.torsor/):

| Area | What it holds |
|---|---|
| `charter.md` | the product charter — the non-negotiable laws (AI-first, everything-is-a-plugin, GraphQL-first, hard-coded Assistant) |
| `architecture/system-patterns.md` · `tech-context.md` | the recurring patterns and the stack/runtime context |
| `architecture/decisions/` | **35 ADRs** — every load-bearing decision (e.g. *ADR 0035: maintain three project SDKs*, *ADR 0032: every deploy bumps the version*). The `torsor ADR NNNN` references throughout `CLAUDE.md` point here |
| `map/` | a compiled map of the repo's modules |
| `memory/journal` | an indexed decision/observation journal |
| `active/context.md` · `progress.md` | the current working context and in-flight progress |

The knowledge base is **semantically indexed** (fastembed `bge-small` embeddings, hybrid RRF retrieval with recency + graph boosting, auto-indexed), and an AI assistant reaches it through the **torsor-helper MCP server** — with token budgets so context stays cheap. In day-to-day development that looks like:

- **`bootstrap_session` / `get_primer` / `get_rules`** — an agent starts a session by pulling the charter, rules, and active context (a ~2k-token primer) so it works *with* the platform's laws, not against them.
- **`recall` / `remember`** — retrieve prior decisions relevant to the task, and record new observations.
- **`record_decision`** — capture a new architectural decision as an ADR (this is how the `torsor ADR NNNN` entries are created).
- **`map_repo` / `impact` / `check_drift`** — map the codebase, assess the blast radius of a change before making it, and detect when code has drifted from the recorded architecture.
- **`handoff`** — snapshot context so the next session (or a fresh agent) resumes without re-deriving everything.

The result: architectural intent is written down once and retrieved on demand, so a new session (human or AI) inherits *why* the platform is shaped the way it is — the same discipline the house rules in [`CLAUDE.md`](CLAUDE.md) enforce, backed by searchable memory.

---

## 🌐 Deployment

**Merging to `main` is a production deploy.** Coolify watches the repo and builds+deploys on every push to `main`; there is no separate ship step. Consequently:

- Every merge **must** bump `MORPHEUS_VERSION` and add a `docs/RELEASE_NOTES.md` entry (Settings → *Version & updates* reads both).
- `/readyz` reports the live version and health; a `deploy-smoke` workflow confirms prod converges on the pushed version.
- Batch local commits into one deploy; don't thrash the builder with rapid merges.

Deployment guides: [`docs/deploy-coolify.md`](docs/deploy-coolify.md) · [`docs/deploy-plesk-nginx.md`](docs/deploy-plesk-nginx.md) · operational recovery in [`docs/OPERATIONS_RUNBOOK.md`](docs/OPERATIONS_RUNBOOK.md).

---

## 📚 Documentation

| Topic | Doc |
|---|---|
| System architecture & request lifecycle | [`ARCHITECTURE.md`](ARCHITECTURE.md) · [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) |
| Product charter & principles | [`CHARTER.md`](CHARTER.md) · [`AI_VISION.md`](AI_VISION.md) |
| Building a plugin | [`docs/PLUGIN_DEVELOPMENT.md`](docs/PLUGIN_DEVELOPMENT.md) |
| Building a theme | [`docs/THEME_DEVELOPMENT.md`](docs/THEME_DEVELOPMENT.md) · [`docs/THEME_EXTENSIONS.md`](docs/THEME_EXTENSIONS.md) |
| Public API (GraphQL/REST) | [`docs/MORPHEUS_API.md`](docs/MORPHEUS_API.md) · [`docs/API_STABILITY.md`](docs/API_STABILITY.md) |
| Agent protocols (MCP/ACP/UCP) | [`docs/MCP_SERVER.md`](docs/MCP_SERVER.md) · [`docs/AGENT_PROTOCOLS.md`](docs/AGENT_PROTOCOLS.md) |
| AI skills | [`docs/SKILLS.md`](docs/SKILLS.md) |
| Compliance (GDPR / EU AI Act) | [`docs/COMPLIANCE.md`](docs/COMPLIANCE.md) |
| Headless usage | [`docs/HEADLESS.md`](docs/HEADLESS.md) |
| Webhooks | [`docs/WEBHOOK_RECIPES.md`](docs/WEBHOOK_RECIPES.md) |
| Operations & incident recovery | [`docs/OPERATIONS_RUNBOOK.md`](docs/OPERATIONS_RUNBOOK.md) · [`docs/PERFORMANCE.md`](docs/PERFORMANCE.md) |
| House rules for AI-assisted work | [`CLAUDE.md`](CLAUDE.md) · [`AGENTS.md`](AGENTS.md) · [`RULES.md`](RULES.md) |
| Release notes | [`docs/RELEASE_NOTES.md`](docs/RELEASE_NOTES.md) |

---

## 🤝 Contributing

Read [`CONTRIBUTING.md`](CONTRIBUTING.md) and the house rules in [`CLAUDE.md`](CLAUDE.md). The short version: it's a plugin unless it's genuinely foundational; add a migration; keep the plugin disable-safe; update the docs in the same commit; and bump the version on anything that deploys.

## 📄 License

[Apache License 2.0](LICENSE) — self-host it, modify it, own it. No platform fees.

<div align="center">

**[▶ See it live at dotbooks.store](https://dotbooks.store)**

*Morpheus OS — commerce you own, run by an AI you can trust.*

</div>
