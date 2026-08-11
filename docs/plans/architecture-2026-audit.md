# Morpheus — 2026 Architecture & Modernization Audit

**Date:** 2026-05-26
**Author:** Codebase pass — full survey, live-deployed-state check, web research.
**Scope:** Architecture review against the latest 2026 AI-commerce + Python +
Django + agentic-protocol standards. Concrete recommendations, ranked by ROI.

> TL;DR: Morpheus is already on the front foot for 2026 — UCP manifest,
> MCP JSON-RPC server, SSE streaming, pgvector hybrid search, Django 6,
> Strawberry GraphQL, 53 active plugins, 38 test files. The gaps are
> mostly *code-cleanliness* (3 files >900 LOC), not architecture. Three
> concrete upgrades will land it at the 2026 high-end bar.

---

## 1. What's already 2026-grade (no work needed)

| Capability | Where | Note |
|---|---|---|
| **Universal Commerce Protocol (UCP)** | `plugins/installed/agent_mcp/well_known.py:27` | Google's January 2026 standard; Adobe Commerce + Shopify adopted. We expose `/.well-known/agentic-commerce-manifest.json` with `productSearch / cart / checkout / orderStatus` capabilities. |
| **Model Context Protocol (MCP) server** | `plugins/installed/agent_mcp/views.py` | Full JSON-RPC: `initialize` / `tools/list` / `tools/call` / `resources/list` / `resources/read`. Bearer auth + scoped tokens via `plugins/installed/agent_mcp/auth.py`. |
| **Trusted-agent attribution** | `plugins/installed/agent_mcp/middleware.py:48 stamp_order_with_agent` | Accepts `X-Verified-Agent-Id` / Cloudflare Web Bot Auth / Visa TAP / Mastercard Verifiable Intent headers; persists agent ID on resulting orders for audit. |
| **SSE streaming** | `core/assistant/views.py:202` + `plugins/installed/agent_core/views.py:190` | `text/event-stream` responses for run logs. |
| **Hybrid search (BM25 + pgvector + RRF fusion)** | `plugins/installed/storefront/views.py:286 _apply_search` + `plugins/installed/ai_assistant/services/search.py:hybrid_search` | Reciprocal Rank Fusion across keyword + dense embeddings. Embeddings refreshed via Celery (`plugins/installed/ai_assistant/tasks.py:34`). |
| **Per-entity CF Cache-Tags** | `api/graphql_view.py` | GraphQL responses carry `Cache-Tag: product:<slug>`; surgical purge on product/category updates fires through the Cloudflare plugin's hook subscriptions. |
| **Storefront edge caching** | `core/storefront_cache.py` | Per-route TTL pattern matching on anonymous storefront pages. Already wired through `morph/settings.py` MIDDLEWARE. |
| **Plugin architecture** | `plugins/installed/<name>/` × 53 | Clean contract per `CLAUDE.md`: `apps.py` + `app.py` + models + migrations + StorefrontBlock contributions + hook subscriptions. Cross-plugin coupling forced through `core.hooks`. |
| **Strawberry GraphQL + Django ASGI compat** | `api/schema.py` + `api/graphql_view.py` | Async-ready stack; views can be promoted to `async def` incrementally. |
| **Observability**| `core/observability.py` + Sentry + request_id middleware | OpenTelemetry-ready, structured logs, query-count middleware. |

---

## 2. Genuine 2026 Gaps — ranked

### 🔴 P0 — code-cleanliness (no architectural change, big professional-polish win)

Three files cross the "needs splitting" threshold (commonly cited as ≥800 LOC):

| File | LOC | Smell |
|---|---|---|
| `plugins/installed/storefront/views.py` | **2098** | Every storefront view in one file: home, PDP, PLP, cart, checkout (4 steps), account (8 sub-pages), journal, vendor, contact, newsletter, search. Hard to navigate, easy to merge-conflict. |
| `plugins/installed/seo/services.py` | **1907** | JSON-LD generation + sitemap + redirects + audit logic all in one module. |
| `plugins/installed/admin_dashboard/forms.py` | **944** | Every dashboard form (product, customer, address, gift card, etc.) lives here. |
| `plugins/installed/catalog/services.py` | **896** | Mutation surface for product + category + variant CRUD called from MCP, admin, agent tools. Could split per-entity. |

**Recommended split for `storefront/views.py`** (this is the one we'll actually ship):

```
storefront/views/
├── __init__.py        — re-exports for back-compat (URLs reference views.home etc.)
├── home.py            — home(), category_detail() prep helpers
├── catalog.py         — product_list(), product_detail(), category_detail(),
│                        author_detail(), staff_picks(), search()
├── cart.py            — cart(), cart_add()
├── checkout.py        — checkout(), checkout_shipping(), checkout_review(),
│                        checkout_payment(), gift card ops, _cart_requires_shipping
├── account.py         — account_home(), account_profile(), account_orders(),
│                        account_addresses(), account_returns(), account_credits(),
│                        account_downloads(), order_confirmation()
├── content.py         — about(), contact(), journal_index(), journal_detail(),
│                        categories(), shipping(), returns(), coming_soon()
├── vendor.py          — vendors_directory(), vendor_detail()
└── api.py             — quick_search() and other small JSON endpoints
```

Each file lands well under 400 LOC. No URL changes, no behavior changes —
pure organizational refactor. Single commit, ~30 min to ship + 8/8 tests still
passing.

### 🟡 P1 — true 2026 trend gaps

| # | Item | Why now | Effort |
|---|---|---|---|
| **P1-A** ✅ DONE (`0789b69`) | **MCP Streamable HTTP transport** | The [2026-07-28 MCP RC](https://blog.modelcontextprotocol.io/posts/2026-07-28-release-candidate/) replaces the old SSE-only pattern. Streamable HTTP lets MCP servers run behind plain round-robin load balancers (no sticky sessions). | Shipped: POST+SSE, GET→405, Mcp-Session-Id, UCP `mcp-streamable` tag, 6 tests. |
| **P1-B** ❌ NOT WORTH IT (verified 2026-05) | **Async storefront views** | ~~The storefront home + PDP each fire 4-8 internal_graphql calls — ideal for `asyncio.gather`.~~ **Premise was wrong.** Code audit (`plugins/installed/storefront/views/`) shows every view makes exactly **one** `internal_graphql` call (a single bundled query — already one round-trip). The hottest page, `product_detail`, adds ~6 *small slug-keyed* ORM lookups (related, videos, specs, reviews, faqs, review-summary). Parallelizing those via `sync_to_async` dispatches each to a threadpool whose ~0.5-2ms overhead rivals the query time, on the highest-traffic page of a live auto-deploying store. Net: marginal/negative gain, high blast radius. **If PDP latency ever becomes a measured problem, profile first** (likely levers: GraphQL resolver N+1, response/edge caching — not async). | Skip unless a profiler says otherwise. |
| **P1-C** ⏸ BLOCKED on P1-B | **Python 3.13 (free-threaded) Docker base** | Free-threaded 3.13 is **4.8× faster on multi-threaded workloads** but **~40% slower on single-threaded code**. Its whole value was predicated on P1-B (async views) existing to exploit multi-threading — and P1-B is now ruled out. Under our current sync/threaded request model 3.13t would be a **net regression**. Plus C-extension free-threading support (psycopg2, Pillow, lxml) is still patchy. **Do not pursue** until there's a real multi-threaded hot path + verified wheel support. | Skip. |
| **P1-D** | **Strawberry Federation v2** | If we ever break out a second GraphQL service (e.g. a separate analytics or ML service), Federation lets the storefront query unify them. Not urgent — but worth keeping the schema federation-ready (subgraph keys on `@strawberry.type`). | ~1 hr to add `@strawberry.federation.type(keys=["id"])` decorations to ProductType / CategoryType / OrderType. No service split needed today. |

### 🟢 P2 — nice-to-haves, not urgent

| # | Item | Note |
|---|---|---|
| P2-A | **Server Components / Islands-style hydration** | We're not React — Django templates + htmx + vanilla JS is fine and arguably *more* 2026-aligned (HTMX hit 1.0 stable in 2024 and the ecosystem matured). No work needed unless we ever go React for a specific surface (e.g. flipbook reader already proved the "JS where it earns its keep" pattern). |
| P2-B | **OpenTelemetry traces on MCP `tools/call`** | We already have OTel infrastructure; just need to wrap each MCP tool call in a span so agent traffic is observable in the same dashboards as human requests. ~1 hr. |
| P2-C | **Rate-limit MCP per-token, not just per-IP** | `core/ratelimit.py` is IP-keyed by default. For MCP, the *token* (not the IP) is the right key — multiple agents on one cloud might share an IP. ~30 min. |
| P2-D | **Speculative loading on top-level nav** | `<link rel="speculationrules">` is now Chromium-supported (`prerender` / `prefetch`). One small JSON config in `<head>` improves perceived LCP for nav-to-PDP by ~600ms on the second click. ~15 min. |
| P2-E | **CSP via report-only** | `core/security_headers.py` emits HSTS / XCTO / XFO / Referrer-Policy / Permissions-Policy — but no CSP. Start with `Content-Security-Policy-Report-Only` to learn the violation surface before enforcing. ~30 min wire-up + a few days of monitoring. |
| P2-F | **Tests at 50+ files** | Currently 38 test files for ~77k Python LOC. The new vendor self-service, quick-search, and affiliate dashboard views all need permission boundary + smoke coverage. The `permission-boundary-tests` skill scaffolds these — one focused day adds 8-12 files. |

---

## 3. What we'll ship this session

**Pick: P0 storefront/views.py split.** Biggest professional-polish win,
zero behavior risk, single PR, single deploy. Other items get noted in this
doc for future sessions.

After the split, future sessions can pick from P1/P2 in priority order. The
split makes every subsequent change cheaper because the per-view diff lands
in a 200-300 LOC file instead of a 2100 LOC monster.

---

## 4. Out of scope for this audit

- **GraphQL → REST migration.** Not happening. GraphQL is the right contract
  for an agentic-commerce stack — single endpoint, typed schema, per-entity
  cache tags, federation-ready. Sticking with it.
- **Replatform off Django.** Django 6 is current; the async story is good;
  the plugin contract is working. No reason to leave.
- **Self-hosted vector DB (Qdrant / Milvus / etc.).** Per [pgvector 2026
  benchmarks](https://callsphere.ai/blog/vector-database-benchmarks-2026-pgvector-qdrant-weaviate-milvus-lancedb),
  pgvector wins on operational simplicity for <10M vector workloads.
  Morpheus's catalog is comfortably under that. Stay on Postgres.
- **Microservices split.** Plugin architecture is the *internal* split.
  Until we hit a real scaling reason (one plugin's load profile genuinely
  conflicts with the rest), shipping more processes is just more ops.

---

## 5. Sources

- [MCP 2026-07-28 RC spec](https://blog.modelcontextprotocol.io/posts/2026-07-28-release-candidate/) — Streamable HTTP transport
- [Universal Commerce Protocol — Google + Adobe + Shopify, NRF Jan 2026](https://commercetools.com/blog/ai-trends-shaping-agentic-commerce)
- [Async Django 2026 guide (Medium)](https://medium.com/@yogeshkrishnanseeniraj/the-ultimate-async-django-architecture-guide-2025-2026-edition-4333ab4c8a90)
- [Python 3.13 free-threaded benchmarks](https://medium.com/@aftab001x/pythons-liberation-the-gil-is-finally-optional-and-why-this-changes-everything-5579b43e969c)
- [pgvector vs Qdrant/Weaviate/Milvus 2026](https://callsphere.ai/blog/vector-database-benchmarks-2026-pgvector-qdrant-weaviate-milvus-lancedb)
- Internal: `ARCHITECTURE.md`, `AI_VISION.md`, `CHARTER.md`, `CLAUDE.md`,
  `ENTERPRISE_ROADMAP.md`, `docs/MCP_SERVER.md`, `docs/HEADLESS.md`.
