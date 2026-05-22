# Morpheus concurrency roadmap

Long-term plan to move Morpheus from "small Django shop" concurrency
toward the throughput needed for a serious open-source ecommerce
platform. Trades off engineering effort against payoff at each step;
each phase can ship independently and the platform stays useful at
every level.

## Where we are now

- gunicorn `--worker-class=gthread --workers=4 --threads=8` →
  **32 concurrent in-flight requests** per container. Per-process
  memory steady at ~250 MB. (commit 108ae65)
- LLM provider SDKs capped at **20 s timeout, max_retries=0** so one
  slow upstream can't burn a worker for the full gunicorn timeout
  window. (commit 5d28ea1)
- Embedding refresh, product description generation, cart recovery,
  Pulse, dynamic pricing all in **Celery** — no LLM work blocks a web
  worker today except interactive paths.
- Embeddings can be **batched** via `refresh_product_embeddings_bulk`
  + `reembed_all_products` Celery tasks.
- `core.circuit_breaker.LLM_BREAKER` short-circuits consecutive
  failures so one downed upstream stops stacking 20 s timeouts.

## Phase 1 — polling endpoint for Linda's JSON mode (~2 hours)

**Problem:** the `/dashboard/assistant/invoke/` endpoint is synchronous.
A user message that triggers a 12 s LLM call holds a thread for the
full duration. The streaming endpoint (`/dashboard/assistant/stream/`)
already avoids this — it yields events as they arrive — but third
party callers and the legacy chat UI still hit the JSON path.

**Shape:**

```
POST /api/llm-tasks/             → returns {task_id, status: "pending"}
GET  /api/llm-tasks/<task_id>/   → returns {status, result?, error?}
```

- Celery task `run_completion_task(task_id, gateway, prompt, system, …)`
  writes the result + error into Django cache (Redis-backed) keyed
  by `task_id`. TTL 1 hour.
- Frontend polls every 500 ms with exponential backoff, gives up at
  60 s and shows a friendly "still working" + manual retry button.

**Acceptance:** Linda's JSON mode replies arrive within 800 ms of
LLM completion; the worker handling the POST returns < 50 ms after
queuing the task.

**Effort:** one Celery task, two view functions, ~80 lines of JS,
one new URL. Pure addition — no migration of existing callers needed.

## Phase 2 — batched embeddings (DONE, this commit)

Already shipped:
- `refresh_product_embeddings_bulk(product_ids)` — up to 200 ids
  per call, swallows per-product errors so one bad row doesn't kill
  the batch.
- `reembed_all_products(batch_size=50)` — fans out chunks to the
  bulk task so the queue stays fluid.

Next-step:
- CSV importer should dispatch `refresh_product_embeddings_bulk` per
  import batch instead of one-task-per-product.

## Phase 3 — async ORM hot paths (multi-week)

**Problem:** the PDP storefront view (the bulk of public traffic)
does ~6 sequential database lookups per render. Sync gthread juggles
them with thread-level concurrency but each request still waits on
the previous DB call before issuing the next.

Django 5.1's async ORM (`.aget`, `.afilter`, `.acreate`) is mature
enough to convert read-heavy paths. Conversion order, hottest first:

1. `plugins/installed/storefront/views.py:product_detail` — single
   biggest gain. ~6 ORM calls per render.
2. `plugins/installed/storefront/views.py:product_list` — paginated
   listing.
3. `plugins/installed/storefront/views.py:home` — featured products
   + curated lists.
4. `plugins/installed/admin_dashboard/views_split/home.py:dashboard_home`
   — admin home tiles (lower traffic but still useful).
5. Cart write paths (`add_to_cart`, `update_cart_item`) — preserve
   transactional semantics; harder to convert.

**Per-view recipe:**

- Wrap the view with `async def`.
- Convert every `.objects.filter(...).first()` → `.objects.filter(...).afirst()`.
- Convert prefetch / select_related blocks via `sync_to_async` only
  when needed; most can be left synchronous inside the same `await`.
- Each model has at least one annotated property (e.g. `.is_on_sale`)
  that touches the related Money field — must remain a regular
  property; convert callers to use values_list where possible.

**Risk:** Django's `request.user` is sync (DB-bound). `info.context.request.user`
inside GraphQL resolvers stays sync — use `await sync_to_async(...)`
when an async resolver needs auth metadata.

**Acceptance:** P99 PDP render < 250 ms under 32 concurrent users on
a fresh container (baseline today: ~800 ms).

**Effort:** 2-3 days per view including tests. ~2 weeks to cover the
5 hot paths.

## Phase 4 — uvicorn ASGI workers

Once Phase 3 is shipping (async ORM in the hot paths), gunicorn can
be swapped from gthread to uvicorn workers via two env vars (see
`scripts/docker-entrypoint.sh`):

```
GUNICORN_APP=morph.asgi:application \
GUNICORN_WORKER_CLASS=uvicorn.workers.UvicornWorker \
GUNICORN_WORKERS=4 \
GUNICORN_THREADS=1
```

Each uvicorn worker handles **hundreds** of concurrent requests via
the asyncio event loop. The memory footprint stays similar (~250 MB)
but throughput on async-converted paths roughly **2-4×**.

Sync paths (cart write, admin dashboard) still work — Django's ASGI
support wraps them in `sync_to_async` transparently. There's no
"flag day" — convert paths to async progressively, run uvicorn the
whole time.

**Acceptance:** Steady-state RPS at the same P95 latency increases
by ≥ 2× compared to the gthread baseline. Memory delta < 30%.

**Effort:** 30 minutes once Phase 3 is ready (env var change + a
canary run).

## Phase 5 — request-path streaming for GraphQL agent reads

For external agents that query slow GraphQL paths (top_products with
a 1-year window, full catalog dumps), accept `Accept: text/event-stream`
on `/graphql/agent/` and stream the response chunked. Reduces the
worker hold-time on the largest queries.

Lower priority — only matters when external agents start pulling
heavy queries, which we don't see yet.

## Phase 6 — pgbouncer transaction mode + read replicas

When async ORM + uvicorn are in place, the next bottleneck is the
database. pgbouncer is already in the stack (memory:
`dotbooks_proxy_chain`) but in session mode. Flip to transaction
mode once we've audited that no view leaks Postgres LISTEN/NOTIFY
or session-scoped temp tables (none today).

Add Postgres read replica for storefront reads when sustained traffic
exceeds 200 RPS. Django's `DATABASE_ROUTERS` lets the catalog GraphQL
queries hit the replica while writes go to primary.

## Out of scope (not on the roadmap)

- Microservice split. Morpheus stays a monolith — the modularity
  comes from the plugin layer, not service boundaries.
- WebSocket-everything. SSE handles the streaming use cases.
- Edge rendering / SSR. Cloudflare Workers in front of a Django
  origin is a different shape entirely; revisit if/when needed.

## Open questions

- Should the polling endpoint (Phase 1) be a generic
  `/api/tasks/<id>/` covering ANY long-running operation, or
  scoped to LLM tasks specifically? Generic is more reusable but the
  task argument set differs by callsite.
- Async ORM + Django signals: do any current signals block on DB
  access in a way that interferes with async? Audit needed before
  Phase 3.

## Decision log

- 2026-05-22 — bumped concurrency to gthread × 32 (commit 108ae65)
  + LLM timeout 20s (commit 5d28ea1). User saw ERR_CONNECTION_RESET
  on the live site; sync workers + slow Packy upstream + lumina-publisher
  external agent were exhausting the 4-worker pool.
- 2026-05-22 — batched embeddings shipped (this commit). Solves the
  fan-out scenario when a CSV import touches thousands of products.
