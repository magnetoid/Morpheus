<div align="center">

# Morpheus OS

### The commerce platform you *own* — and can talk to.

**Describe your shop in one sentence → a real store in ~20 seconds.**
**Turn any feature on or off like an app.**
**Hand the back office to an AI staff member who learns your store, briefs you every morning, and proposes her own upgrades.**

Morpheus is an open-source, Shopify-grade commerce platform where **AI is a built-in co-worker, not a monthly add-on**, every feature is a plugin you can switch off without a trace, and the whole thing runs on infrastructure **you** control. When the AI wants to change *code*, the change is reviewed by a **panel of independent LLMs** and then by **you** — never merged by a machine alone.

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Live store](https://img.shields.io/badge/live-dotbooks.store-ff5722.svg)](https://dotbooks.store)
[![Own it](https://img.shields.io/badge/self--host-no%20platform%20fees-16a34a.svg)](#who-its-for)
[![Plugins](https://img.shields.io/badge/plugins-60%2B%20toggleable-blue.svg)](#how-its-built)
[![AI operator](https://img.shields.io/badge/AI-built--in%20operator%20(Linda)-e11d48.svg)](#meet-linda)
[![Agent-ready](https://img.shields.io/badge/agentic%20commerce-MCP%20%2F%20ACP%20%2F%20UCP-7c3aed.svg)](#future-proof-for-ai-shopping)
[![SEO / AEO](https://img.shields.io/badge/found%20by-Google%20%2B%20AI%20answers-eab308.svg)](#get-found)
[![Stack](https://img.shields.io/badge/django%206-postgres-2563eb.svg)](#tech-stack)

### [▶ See it live](https://dotbooks.store) · [🚀 Launch your own](#quick-start) · [🧠 Who it's for](#who-its-for)

[Why Morpheus](#why-morpheus) · [Who it's for](#who-its-for) · [See it work](#see-it-work) · [Meet Linda](#meet-linda) · [How it's built](#how-its-built) · [How it compares](#how-it-compares) · [Quick start](#quick-start) · [Docs](#documentation)

</div>

---

<div align="center">

### The one-liner

**Morpheus is a complete commerce platform where every feature is a switch-off-able app, and the back office ships with Linda — an AI staff member who remembers your store, works before you wake up, and writes her own new tools under a review gate that ends at *your* approval.**

*Not a chatbot bolted onto a store. A store built for an operator who happens to be an AI.*

</div>

---

## Why Morpheus

Most commerce platforms make you choose: rent a polished SaaS and give up ownership (per-seat fees, app-store revenue share, your data on someone else's servers, one policy change away from being de-platformed) — or self-host something powerful but bare, and build the modern parts yourself.

Morpheus refuses that trade. It's **batteries-included like Shopify, ownable like open source, and AI-native from the kernel up.**

| What you get | What it means for your business |
|---|---|
| **⚡ Launch in a day** | Type one sentence — *"a modern Japanese tea shop selling single-estate matcha and hand-thrown ceramics"* — and get a real storefront with brand voice, categories, and priced products in ~20 seconds. Then refine, don't start from zero. |
| **🧠 An AI staff member, not an AI subscription** | Linda runs on a real agent kernel inside the platform. She answers questions *and acts* — pulls orders, updates prices, drafts copy, reviews your last 24 hours before you log in. Do more with a leaner team. |
| **🔒 You own everything** | Apache-2.0, self-hosted. No per-seat tax, no app-store cut on your revenue, no lock-in. Your code, your database, your customers — on infrastructure you control. Fork it, audit it, keep it forever. |
| **🧩 Only run what you need** | 60+ features ship as **apps you toggle**. Reviews, loyalty, subscriptions, B2B, multi-currency, a 3D storefront — flip them on when you need them, off when you don't. Turning one off cleanly removes every trace of it. |
| **🤖 Future-proof for AI shopping** | Built-in support for the protocols AI shopping agents use to browse and buy (MCP, Agentic Commerce Protocol, Universal Commerce Protocol, Visa/Mastercard agent payments). When customers shop *through* ChatGPT or Perplexity, your store is already reachable. |
| **🔎 Get found — by Google *and* AI answers** | A full 2026 SEO + AEO stack: rich structured data, an AI-crawler-aware sitemap, `/llms.txt`, auto-generated Google Web Stories, and per-product markdown feeds so answer engines cite you. |

**The honest version:** Morpheus is younger than Saleor or Shopify. What it trades in raw runtime-hours it makes back in AI-native onboarding, an AI operator no one else ships, and code you actually own. See the candid trade-offs in [How it compares](#how-it-compares) — we don't hide the gaps.

**Live proof:** **[dotbooks.store](https://dotbooks.store)** runs on Morpheus today — storefront, checkout, AI operator, and all.

---

## Who it's for

Morpheus speaks to four people. Here's what each one gets.

### 🚀 Founders

> *"Launch this week, not next quarter — and never outgrow it."*

- **One sentence to a live store.** The [one-prompt bootstrap](#see-it-work) writes your brand voice, catalog structure, and starter products so day one looks like month three.
- **Batteries included.** Catalog, cart, checkout, payments, shipping, tax, SEO, email, analytics, an AI operator — no stitching six SaaS tools together.
- **No ceiling.** It's a real platform, not a template. When you need B2B pricing, subscriptions, a marketplace, or a headless front end, it's an app toggle away — not a migration.

### 🎨 Brand owners

> *"Your brand, your rules, your storefront — not a marketplace clone."*

- **A storefront that looks like you.** Fully themeable (the shipped `dot_books` theme is editorial and fast); your brand voice propagates into every AI-written description, email, and answer.
- **Total control.** Turn features on and off like apps. No forced redesigns, no surprise deprecations, no algorithm deciding who sees your shop.
- **You can't be de-platformed.** It's your install. Your customer list and order history live in *your* database, exportable any time.

### 📈 CEOs & operators

> *"Do more with a leaner team, and own your economics."*

- **A back office that runs itself.** Linda handles routine ops and posts a proactive daily briefing before you log in. Fewer clicks, fewer tools, fewer hires to scale.
- **Own your margins.** No per-seat licenses, no app-store revenue share, no platform transaction fee stacked on top of your payment processor. Self-hosting cost, not a percentage of GMV.
- **Governed by design.** RBAC, a tamper-evident audit trail, a GDPR/ePrivacy master switch, and every AI action logged with provenance — so "the AI did it" is always accountable.

### 🛠️ Developers

> *"A kernel you can actually reason about."*

- **The core is small; everything else is a plugin.** Add a feature by dropping a self-contained package in `plugins/installed/` — its own models, migrations, dashboard pages, storefront blocks. Disabling it removes every surface it added.
- **No spaghetti.** Plugins never import each other; they coordinate over an event bus. A crashing plugin is isolated and logged — it can't take down its siblings.
- **AI-native DX.** A real agent kernel, a Model Context Protocol server, GraphQL + REST + a Python SDK, versioned prompts, capability scopes, and a lossless agent trace. Ship tools an AI can safely call.

---

## See it work

### One prompt → a live store in ~20 seconds

A merchant types one sentence, and the [`store_bootstrap`](plugins/installed/store_bootstrap/) app calls the configured LLM to generate a brand voice, 4–6 categories, and 10–12 starter products — complete with copy, prices, and SKUs.

```
/dashboard/apps/store_bootstrap/start/
  →  "A modern Japanese tea shop selling single-estate matcha, sencha, and ceramics"
  →  LLM → strict-JSON plan → categories + priced products written to your catalog
  →  brand voice saved once, then reused by every future AI generation
  →  a real storefront at https://your.shop/products/
```

Re-running the same sentence re-uses what it already created instead of duplicating it. **No other open-source commerce platform ships this.**

### Or just look at one running in production

**[dotbooks.store](https://dotbooks.store)** — a full storefront, checkout, and AI back office on Morpheus.

---

## Meet Linda

**Linda is the difference between "a store with an AI chatbot" and "a store built for an AI operator."**

She isn't a widget bolted onto the dashboard — she's a first-class part of the platform that keeps working even when individual features fail. What she does, in plain terms:

- **Answers and acts.** "How many orders shipped late this week?" "Bump the price on the matcha bundle." "Draft a launch email in our voice." She reads your data and — with your confirmation — changes it.
- **Remembers your store.** She recalls the things you've told her (where you ship from, your return policy, your tone) and surfaces the right one for the question you're asking now.
- **Works before you wake up.** An opt-in daily briefing reviews the last 24 hours and posts what needs your attention, with one-click actions.
- **Improves herself — safely.** When she keeps hitting the same missing capability, she can *draft a new tool for it*. That draft passes an automated safety scan, then a **panel of independent AI models voting on it**, then lands in an approval queue where **you** click yes or no. Nothing self-modifying ships without a human. (Off by default; opt-in.)

**Every action is scoped, rate-limited, logged, and reversible where it matters** — and any write ("cancel this order") refuses to run without explicit confirmation.

<details>
<summary><b>For the technically curious — how deep does it go?</b></summary>

Linda is a hard-coded `Assistant` in [`core/assistant/`](core/assistant/) (never a plugin), with **50+ first-class tools** spanning reads (orders / products / customers / analytics / content / media / metafields), confirmation-gated writes, cross-session **semantic memory**, self-learning **skills**, sandboxed `run_python` multi-tool composition, and the gated self-development pipeline above. She runs on a real agent **kernel** ([`core/agents/`](core/agents/)) — an LLM tool-use loop with provider abstraction (OpenAI / Anthropic / Gemini / OpenRouter / Grok / Ollama), capability scopes, versioned prompts, brand-voice-aware system prompts, and a lossless trace persisted for audit. Full tool catalogue: [`get_default_tools`](core/assistant/tools/__init__.py). Policy: [ADR 0028](.torsor/architecture/decisions/) (propose-only self-coding).

</details>

---

## How it's built

*The part developers and technical founders care about. Everyone else can skip to [How it compares](#how-it-compares).*

### The core is small. Everything else is a plugin.

The kernel handles only what every store needs — catalog, cart, checkout, fulfillment, plus foundations (auth, the events bus, settings, i18n, observability, the AI + safety boundary). **Reviews, loyalty, markets, CMS, SEO, payment gateways, subscriptions, B2B, the agent layer, even a 3D storefront — all self-contained apps** under [`plugins/installed/`](plugins/installed/) you can enable, disable, or fork without touching the engine. The source of truth for what ships enabled is [`MORPHEUS_DEFAULT_PLUGINS`](morph/settings.py) — never a hard-coded count.

### The modularity contract

> **A theme exposes named slots → plugins fill those slots → disabling a plugin removes its surfaces.**

No dangling references, no half-wired features. Two plugins can target the same slot (ordered by priority) without knowing about each other, because they coordinate through the [`core.hooks`](core/hooks.py) event bus — **never** by importing one another. A broken plugin `ready()` is logged and skipped; its siblings keep loading. See [`docs/PLUGIN_DEVELOPMENT.md`](docs/PLUGIN_DEVELOPMENT.md) and [`docs/THEME_DEVELOPMENT.md`](docs/THEME_DEVELOPMENT.md).

```python
# in a plugin's plugin.py — the plugin decides what it contributes
class ReviewsPlugin(Plugin):
    name = "reviews"
    def contribute_storefront_blocks(self):  # → appears on the PDP
        return [StorefrontBlock(slot="pdp_below_description", template="reviews/block.html")]
    def contribute_dashboard_pages(self):     # → appears in the sidebar
        return [DashboardPage(slug="reviews", view="...", nav="main")]
# Delete the folder → the feature is gone. Toggle it off → every surface disappears.
```

### Agentic-commerce & integration surface

- **AI clients can transact directly.** A Model Context Protocol (MCP) server cluster exposes audience-scoped surfaces (storefront / cart / checkout / admin), plus discovery for the Universal Commerce Protocol, Agentic Commerce Protocol (OpenAI/Stripe), and Visa/Mastercard agent-payment handshakes at `/.well-known/`.
- **Standard APIs too.** Strawberry **GraphQL** + Django REST + signed (HMAC-SHA256) webhook fanout + a Python SDK.
- **Event-sourced.** Every state change emits a hook *and* writes to a transactional outbox shipped to NATS JetStream — replayable and auditable.

### <a id="get-found"></a>Found by Google and AI answer engines

A dedicated [`seo`](plugins/installed/seo/) app closes the 2026 SEO + AEO loop: a 15-bot AI-crawler matrix, per-object JSON-LD (Product/Book/Review/Article/FAQ/Breadcrumb/Organization), `/llms.txt`, per-product markdown export, IndexNow auto-ping, RSS/Atom feeds, hreflang, sitemap index + image/news sub-sitemaps, and a paste-a-slug SEO inspector. A companion [`webstories`](plugins/installed/webstories/) app auto-generates a valid Google AMP Web Story per product.

### <a id="future-proof-for-ai-shopping"></a>Hardened by default

Staff sign-in is plugin-modular: [`staff_mfa`](plugins/installed/staff_mfa/) adds a TOTP second factor, [`staff_sso`](plugins/installed/staff_sso/) federates to your OIDC/SAML IdP — and **SSO cannot bypass MFA** (the SSO adapter runs the same second-factor gate). `DEBUG=False` by default, secrets required in prod, RBAC capabilities, per-user rate limits on the agent endpoint, secret-redaction before anything reaches an LLM, and a `@safe_db` degrade-don't-crash path. Full list: [Security defaults](#security-defaults).

---

## How it compares

Saleor, Medusa, and Vendure are excellent self-hostable platforms. Morpheus's bet is **plugin-native modularity + a built-in agent layer**: the multi-protocol agent gateway the big players are racing toward ships here today, behind toggleable apps rather than a hosted add-on.

| Capability | Morpheus | Saleor | Medusa | Vendure |
|---|:---:|:---:|:---:|:---:|
| Always-on AI merchant operator (Linda) | ✅ | — | — | — |
| Self-learning agent (memory + reflection + skills) | ✅ | — | — | — |
| Self-coding under multi-LLM consensus + owner approval | ✅ | — | — | — |
| One-prompt store bootstrap | ✅ | — | — | — |
| MCP / ACP / UCP / agent-payment surfaces | ✅ | — | — | — |
| AI-crawler sitemap + `/llms.txt` + per-product markdown | ✅ | — | — | — |
| Auto-generated Google Web Stories per product | ✅ | — | — | — |
| Staff SSO (OIDC + SAML) that **cannot bypass MFA** | ✅ | — | — | — |
| Plugin crash isolation | ✅ | ✱ | ✱ | ✱ |
| GraphQL + signed webhook fanout | ✅ | ✅ | ✅ | ✅ |
| Years of production runtime at scale | 🟡 younger | ✅ | ✅ | ✅ |

### Is Morpheus right for you? (the honest answer)

We won't pretend. Saleor has ~5 years of production mileage Morpheus hasn't logged yet. If you're choosing today, here's the candid trade-off:

- **Pick Morpheus** if you're a founder, brand, or agency **launching this year** with a small/mid catalog and you want AI-driven onboarding, an AI operator, a distinctive storefront, and **code you own outright**.
- **Pick Saleor** if you're a **$50M+ GMV merchant migrating off Shopify Plus today** and need battle-tested multi-warehouse/multi-currency depth and years of load-tested scale *right now*.

Where Saleor is still ahead — and where we're closing the gap — is tracked openly: maturity & runtime hours (🟡 closing), GraphQL completeness (🟡), multi-warehouse depth (🔴 real gap), published performance-at-scale numbers (🔴), and ecosystem/tutorials (🟡). Details in [`CHANGELOG.md`](CHANGELOG.md) and the [enterprise roadmap](ENTERPRISE_ROADMAP.md).

---

## Quick start

### Deploy to Coolify (recommended)

```text
+ New Resource → Docker Compose
  Repo:         https://github.com/magnetoid/morpheus
  Compose file: docker-compose.yml          ← default; no override needed
  Env vars:     paste from .env.coolify.example
  Domain:       bind your.domain.com to the `web` service
```

The default `docker-compose.yml` ships **web + worker + beat + postgres + redis + pgbouncer**. The web container waits for the DB, runs `migrate` + `collectstatic`, then serves via gunicorn. Full guide: [`docs/deploy-coolify.md`](docs/deploy-coolify.md).

### Run it locally

```bash
git clone https://github.com/magnetoid/morpheus && cd morpheus
cp .env.example .env                     # set SECRET_KEY, DATABASE_URL
docker compose up                        # web + worker + beat + postgres + redis
# → http://localhost:8000  ·  dashboard at /dashboard/
```

A no-Docker SQLite path for quick request/response work is in [`docs/QUICK_START.md`](docs/QUICK_START.md). Add an LLM key (any supported provider) to unlock Linda and the one-prompt bootstrap.

---

## Tech stack

- **Backend:** Python 3.12, Django 6
- **APIs:** Strawberry GraphQL + Django REST Framework + JSON-RPC 2.0 (MCP)
- **Data:** PostgreSQL (Supabase recommended) · Redis + Celery · NATS JetStream event bus
- **AI:** pluggable LLM providers — OpenAI / Anthropic / Gemini / OpenRouter / Grok / Ollama
- **Ops:** OpenTelemetry → Prometheus / Grafana / Loki + Sentry · multi-stage non-root Docker · k8s manifests
- **SDK:** [`services/sdk_python`](services/sdk_python/)

### <a id="security-defaults"></a>Security defaults (changed from a vanilla Django template)

`DEBUG=False` and required secrets in prod · HMAC-SHA256 on every webhook · GraphQL depth/alias caps + 5xx masking with `request_id` · rate-limited `/graphql`, `/v1/`, and a **20 req/min/user cap on the agent endpoint** · Sentry scrubbing of tokens/cookies/secrets · RBAC capabilities (audit-logged) · **assistant writes require `confirmed=True`** · `settings.list` auto-redacts any `*_key`/`*_secret`/`*_password`/`*_token`.

---

## Roadmap

A live snapshot, rebuilt every couple of weeks; **[done]** items are already in `main`. The north-star is the [cutting-edge open-core plan](docs/plans/cutting-edge-open-core-2026-07.md).

- **Now:** headless GraphQL/REST completeness · Web Stories v2 (per-panel editor) · public API deprecation-window contract.
- **Mid-term:** multi-warehouse stock reservation · channel-specific tax + FX-aware refunds · marketplace payout automation (Stripe Connect / Wise) · background-agent timeline.

Recently shipped lands in [What's new](#whats-new) below; full history in [`CHANGELOG.md`](CHANGELOG.md).

---

## Documentation

**Start here:** [`CHARTER.md`](CHARTER.md) (the project constitution — mission, the Laws, what Morpheus is and is NOT) → [`ARCHITECTURE.md`](ARCHITECTURE.md) (system design, plugin lifecycle) → [`docs/PLUGIN_DEVELOPMENT.md`](docs/PLUGIN_DEVELOPMENT.md) + [`docs/THEME_DEVELOPMENT.md`](docs/THEME_DEVELOPMENT.md) (build a plugin or theme) → [`SKILLS.md`](SKILLS.md) (named procedures for common tasks).

**Ops & stability:** [`docs/API_STABILITY.md`](docs/API_STABILITY.md) · [`docs/HEADLESS.md`](docs/HEADLESS.md) · [`docs/WEBHOOK_RECIPES.md`](docs/WEBHOOK_RECIPES.md) · [`docs/OPERATIONS_RUNBOOK.md`](docs/OPERATIONS_RUNBOOK.md) · [`docs/RELEASE_NOTES.md`](docs/RELEASE_NOTES.md).

---

## What's new

- **Dashboard polish + About page + full-width storefront (v0.2.28)** — A design-system consistency + micro-animation pass across the dashboard (breadcrumbs deduplicated, dark-mode fixes, staggered card entrances — all disabled under `prefers-reduced-motion`), a new **Settings → About Morpheus** page (a plain-language overview + a live catalogue of every installed app), and a **full-width, edge-to-edge storefront** on the `dot_books` theme (checkout stays comfortably bounded). New process rule ([ADR 0032](.torsor/architecture/decisions/)): every production deploy bumps `MORPHEUS_VERSION` + adds a `RELEASE_NOTES.md` entry, so the in-dashboard changelog never drifts behind what's live.
- **Linda self-learning wave (v0.2.27)** — the AI operator's self-improvement loop went live: semantic memory recall, a post-run reflection loop that retires chronically-failing skills, an opt-in proactive daily briefing, and propose-only self-coding behind a multi-LLM consensus panel + owner-approval queue. Every decision audited.
- **Agentic-commerce wave** — the MCP server cluster, confirmation-gated assistant write tools, authoritative `cartTotals` GraphQL, a Shopify migration UI, and brand-voice config flowing into every AI generation.
- **Discovery wave (SEO + AEO 2026)** — 15-bot AI-crawler matrix, per-object JSON-LD, `/llms.txt`, per-product markdown export, IndexNow auto-ping, Google Web Stories, and Core Web Vitals RUM feeding a dashboard panel.
- **Foundations wave** — the central `media` library, schema-less `metafields` on any model, and the Shopify-pattern dashboard (sticky save bar, status tabs, real analytics).

Full history: [`CHANGELOG.md`](CHANGELOG.md) · in-dashboard changelog: **Settings → Version & updates**.

---

## Contributing

PRs welcome. The bar, briefly: **new behavior comes with tests**; **new domains are plugins, not top-level Django apps**; **honor the security defaults**; and **assistant write tools take `confirmed: bool`** and refuse to mutate state without it. Full guidelines and the plugin skill: [`SKILLS.md`](SKILLS.md).

---

## License

[Apache 2.0](LICENSE) — use it, fork it, sell with it, own it.

<div align="center">

**[▶ See it live](https://dotbooks.store)** · **[🚀 Launch your own](#quick-start)** · **[📚 Read the docs](#documentation)**

*Morpheus OS — a commerce platform you own, that works while you sleep.*

</div>
