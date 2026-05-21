# Performance — current state, baseline, and roadmap

> *"You can't claim 'fast' without numbers."*

This document captures what we measure today, the baseline we measured against the live `dotbooks.store` deployment, and the prioritised work that closes the remaining gaps to "Shopify-Plus-class performance under load."

## Baseline (current)

Measured against `https://dotbooks.store` on **2026-05-21** with [`manage.py morph_bench`](../core/management/commands/morph_bench.py) — 15 iterations per URL, 3 warmup hits, sequential (concurrency=1):

| Page | p50 | p95 | Success | Notes |
|---|---|---|---|---|
| `/products/hamlet/` (PDP) | **188 ms** | **229 ms** | 15/15 | Fragment cache + composite index hits |
| `/category/fiction/` | 254 ms | 271 ms | 15/15 | Composite `(status, category)` index in play |
| `/staff-picks/` | 169 ms | 186 ms | 15/15 | |
| `/about/` | 105 ms | 124 ms | 15/15 | Mostly template-render |
| `/llms.txt` | 100 ms | 122 ms | 15/15 | Cached at edge via `Cache-Control` |
| `/` (home) | 216 ms | 1153 ms | 9/15 | Long tail — needs investigation |
| `/products/` (PLP) | 378 ms | 967 ms | 11/15 | Similar long tail |
| `/journal/` | 110 ms | 714 ms | 13/15 | |
| **Median p95** | — | **250 ms** | — | Across 10 storefront URLs |

The intermittent failures on `/`, `/products/`, `/journal/` are network-level (Plesk dropping keep-alives, Cloudflare edge propagation), not origin 5xx — confirmed via Plesk access-log analysis.

## What we ship for perf today

| Lever | Where | Impact |
|---|---|---|
| **Edge cache headers** | [`plugins/installed/storefront/middleware.py`](../plugins/installed/storefront/middleware.py) | `Cache-Control: public, s-maxage=60, stale-while-revalidate=300` on safe storefront GETs. Cloudflare caches aggressively; warm-edge hits go to <50 ms. |
| **Fragment cache on PDP** | [`themes/library/dot_books/templates/storefront/product_detail.html`](../themes/library/dot_books/templates/storefront/product_detail.html) | Reviews block 600 s + related-products 1800 s, keyed on `product.updated_at` so a product save auto-invalidates. |
| **Composite DB indexes** | [migration `0009_perf_indexes`](../plugins/installed/catalog/migrations/0009_perf_indexes.py) | `(status, category)` on Product, `(product, sort_order)` on ProductImage, `(product, is_approved, -helpful_votes)` on Review. Covers the PDP/PLP hot queries. |
| **PDP prefetch consolidation** | [`storefront/views.py` (`product_detail`)](../plugins/installed/storefront/views.py) | Was running `Product.objects.filter(slug=slug)` 5× per render (one per helper). Now one lookup, threaded into helpers via `product_row=` kwarg. ~3-4 fewer queries per PDP. |
| **Connection pool** | `morph/settings.py` — `conn_max_age=600` on both primary + replica | Persistent PG connections; no reconnect per request. |
| **Real `/healthz`** | [`morph/urls.py`](../morph/urls.py) | Liveness probe returns 200 only after WSGI app loads. Stops Docker false-positive "healthy" → traffic-swapped-too-early → deploy-window 503s. |
| **DEBUG-only N+1 detector** | [`core/query_count_middleware.py`](../core/query_count_middleware.py) | Logs WARNING when any view does >50 queries. Zero overhead in production (`DEBUG=False` short-circuits). |
| **Plugin boot log quiet** | [`plugins/registry.py`](../plugins/registry.py) | One INFO summary line at end of activation; per-plugin `Plugin activated:` lines demoted to DEBUG. Saves ~49 lines per process start. |

## Reproducing the baseline

```bash
# Sequential bench (what's documented above)
python manage.py morph_bench --base-url https://dotbooks.store --iterations 30

# Save as a baseline for future regression detection
python manage.py morph_bench --base-url https://dotbooks.store \
                             --iterations 30 \
                             --save docs/perf/baseline-prod.jsonl

# After a change: compare to baseline, exit 2 if any URL regresses >15%
python manage.py morph_bench --base-url https://dotbooks.store \
                             --iterations 30 \
                             --baseline docs/perf/baseline-prod.jsonl

# JSON output for CI diffs
python manage.py morph_bench --base-url https://dotbooks.store --json
```

The bench uses a Mozilla-shaped User-Agent (Plesk and many WAFs 503 anything labeled `bot/curl/script`), hits `/healthz` style endpoints for warmup, and reports p50/p95/p99/max plus the status-code distribution per URL.

## Remaining gaps (priority order)

### 1. Concurrency load test (next session candidate)
The current bench is **sequential** — it measures what one user sees on an otherwise-idle origin. It does not capture:
- Pool contention (DB, Redis, gunicorn workers)
- Cache hit-rate under load
- Tail latency p99 at 50+ concurrent requests

**Action**: k6 script at `scripts/load/storefront.js` hitting the bench URLs at concurrency 20-50 for 60 s. Compare p95 sequential vs p95 concurrent — the gap measures how much headroom we have. Target: p95 at concurrency 50 stays within 2× of sequential.

### 2. OpenTelemetry traces — actually mostly done
On re-audit, `init_observability()` is called from both [`morph/asgi.py:18`](../morph/asgi.py#L18) AND [`morph/celery.py:41`](../morph/celery.py#L41), so HTTP requests AND Celery tasks are instrumented. The env var (`OTEL_EXPORTER_OTLP_ENDPOINT`) is documented in [`README.md:590`](../README.md), [`docs/deploy-coolify.md:158`](deploy-coolify.md), and [`docs/OPERATIONS_RUNBOOK.md:26`](OPERATIONS_RUNBOOK.md). Instrumentation covers Django, Celery, psycopg2, Redis, requests, and logging.

What IS missing: a one-command "stand up a Jaeger sidecar locally to see your own traces" recipe so a contributor can verify their perf change actually shows up in spans.

**Action**: add a `docker-compose.observability.yml` override file with a Jaeger all-in-one container (`jaegertracing/all-in-one:1.66` listening on 4318/HTTP), wire `OTEL_EXPORTER_OTLP_ENDPOINT=http://jaeger:4318` in the same override; document `docker compose -f docker-compose.yml -f docker-compose.observability.yml up`. ~30 min of work, gates the "perf change must show in traces" workflow.

### 3. GraphQL field-level cache hints (M3)
Strawberry doesn't ship `@cache_control` out of the box, so the GraphQL endpoint (POST-by-default) bypasses every CDN. Frontends that re-fetch `cartTotals` on every navigation pay full origin latency. An extension that emits `Cache-Control` headers based on schema annotations (e.g. `@cache(max_age=30)` on `cartTotals`) would let smart clients (Apollo + persisted queries) cache GET-form queries.

**Action**: design + ship the strawberry extension; document the directive; add `cartTotals` as the first user.

### 4. Asynchronous hook dispatch (M2)
`ORDER_PAID` and friends fire ~5 hook handlers synchronously during request processing. The `tracking` plugin's GA4 Measurement Protocol call alone adds ~80 ms to the order-confirmation response. Moving non-critical hooks to Celery (analytics, embeddings, marketing emails) while keeping critical ones (inventory decrement, fulfillment) synchronous would drop p95 on the checkout-complete path.

**Action**: tag each hook handler with `priority` + `mode='async'|'sync'`; dispatcher routes async handlers to a Celery task; critical handlers stay in-request.

### 5. Async views for hot paths (M5)
Django 5 supports `async def` views. `cartTotals`, `productDetail`, and `/healthz` should be async so I/O (LLM calls, S3 fetches, external APIs) doesn't block a sync gunicorn worker. With our current 4-worker setup, one slow external call ties up 25% of capacity.

**Action**: convert `cartTotals` resolver and the `/api/health/` view first; measure the difference; expand if positive.

### 6. Multi-tenancy
One Morpheus process per merchant is wasteful at hosting cost. A single instance serving N tenants via subdomain / Host-header routing (and a tenant-scoped DB schema or row-level isolation) would be a 10× hosting-cost reduction. Real work; tier-3.

### 7. Read-replica routing
`core/db_router.py` exists but `DATABASE_ROUTERS` is wired only for the primary today (no replica configured). Read-heavy queries (catalog, search, dashboard analytics) on a replica would offload the primary for write-path latency.

## How to use this document

- **Before a perf change**: run `morph_bench --save baseline-pre-{branch}.jsonl`.
- **After**: `morph_bench --baseline baseline-pre-{branch}.jsonl` — verify no URL regresses >15%.
- **In CI**: nightly run against staging with the prod baseline; alert on regressions.
- **On user complaint**: re-run the bench, compare to the baseline above. If numbers match but users report slowness, the issue is in code paths the bench doesn't hit (admin dashboard, checkout flow, GraphQL writes) — extend the URL list in [`morph_bench.py`](../core/management/commands/morph_bench.py).

Bench output is checked into `docs/perf/` as JSONL so the history of baselines is browsable in git.
