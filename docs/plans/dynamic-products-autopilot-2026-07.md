# Dynamic Products → Merchandising Autopilot (2026-07)

> **Status:** approved 2026-07-06 — user chose **Phases 1–3** (zero new deps).
> Deep web research (5 agents) + Morpheus infra map complete. Build inline,
> commit per phase, **push only on "ship"** (batch — Coolify deploy discipline).

## Goal

Turn `plugins/installed/dynamic_products` from a **manual, fake-AI** merchandising
plugin into a **real, self-updating, self-optimizing, self-configuring** per-visitor
recommendation engine — reusing existing Morpheus infra, **pure-Python, zero new
dependencies** (Phases 1–3). Phase 4 (LightGBM) is deferred (needs native deps →
the v0.2.8 deploy-window landmine; the whole platform is currently numpy-free).

## The problem (current state, verified)

- `probability_grid` strategy sorts by `DynamicGridItem.purchase_probability`, but
  `calculate_grid_probabilities()` (`services.py:211`) is a **mock**: every input is
  `getattr(product, 'recent_sales_score', 0.5)` (attrs that never exist → constant
  ~0.4 for all), `total_stock` via `hasattr` is always `10`, `W_INVENTORY` is
  declared then dropped from the sum. **Never scheduled** (no `tasks.py`, no beat).
- Everything is **manual** (merchant hand-creates every `DynamicBlock`).
- `personalisation.recompute_copurchases_task` has **no beat entry** → `CoPurchaseScore`
  never refreshes (docstring lies). Also uses invalid statuses `'paid'`/`'completed'`.
- `experiments.results_for()` has **zero consumers** → winners never feed back.

## Research → architecture (what every agent converged on)

Cheap **propensity score** + **Thompson-sampling reranker** (value-weighted reward,
purchase ≫ cart ≫ view; ~semi-personalized per segment) + nightly Celery-beat
refresh + impression→outcome logging + **LLM used offline** (never per-request) to
author config behind a human checkpoint. Guardrails: exploration floor, cold-start
priors, per-category diversity cap. LightGBM is the eventual model but overkill
until the loop exists.

## Morpheus infra to build on (condensed map — file:line)

READY:
- **analytics** `AnalyticsEvent` (`analytics/models.py:78`): `kind` (choices incl.
  `product_view, cart, checkout, purchase`), `product_slug` (indexed), `revenue`
  (MoneyField, label), `session`/`customer` FKs, `created_at`, `scroll_depth`,
  `duration_ms`. `AnalyticsSession` (`:28`): `cookie_id`, `device`, `geo_location`,
  `utm_*`, `referrer`, `event_count`, `is_consented`. Written via `record_event()`
  (`analytics/services.py:200`) fanned from hooks (`analytics/plugin.py:34`).
  `session_duration` field exists but is **never written** → derive dwell from
  `last_seen_at − first_seen_at`.
- **orders** `Order.status` FSM (valid: `pending,confirmed,processing,
  partially_fulfilled,fulfilled,shipped,delivered,cancelled,refunded`),
  `Order.placed_at`, `OrderItem(order,product,quantity)` (`orders/models.py:280`;
  **no** `OrderItem.created_at` → use `order__placed_at`). No canonical paid-status
  helper (hardcoded + inconsistent across plugins).
- **inventory** `StockLevel` (`inventory/models.py:30`): `quantity`, `reserved_quantity`,
  `available_quantity` = property `max(0, quantity-reserved)`; keyed by **variant+warehouse**.
  Product stock = `SUM(quantity-reserved)` over `product.variants`. **Optional plugin →
  lazy import, fail-soft.** `Product` has NO stock field (mock's `total_stock` never existed).
- **catalog** `Product`: `price` (MoneyField `.amount`), `is_featured` (indexed),
  `is_on_sale` prop, `category`, `tags.names()`, `status`, `track_inventory`,
  `primary_image`. `ProductReview` (rating, is_verified_purchase).
- **personalisation** `rank_for_visitor(request, products, *, surface='')`
  (`services.py:267`) — per-visitor reorder, consent-gated, **already subscribed to
  `PRODUCT_LIST_REORDER`** (`plugin.py:26`, pri 50) across 6 storefront surfaces.
  `recompute_copurchases(*, window_days=90, top_k=12)`, `related_to(product, *, k)`,
  `CoPurchaseScore(anchor,related,score)`. `_has_consent(request)` (cookie `morph_consent`).
- **experiments** `Experiment/Assignment/Exposure`, `variant_for(request, key)`,
  `record_conversion(...)`, `results_for(exp)` (Wald z, lift). `pick_variant(visitor_id)`
  deterministic. ORDER_PLACED→conversion wired but anonymous (`v:`) unattributed
  (Order has no `metadata`/visitor field).
- **Celery**: `autodiscover_tasks()` finds every `tasks.py`; `CELERY_BEAT_SCHEDULE={}`
  filled by plugins via `register_celery_beat(name, entry)` / inline `setdefault` +
  `crontab`; `register_celery_tasks(module)` in `ready()`. **Eager only under tests.**
- **hooks** `PRODUCT_LIST_REORDER` (filter, value=list[Product], kwargs request/surface),
  `PRODUCT_VIEWED` (fire, product/customer/request), `ORDER_PLACED` (fire, order).
- **embeddings** `core.embeddings.embed()`/`cosine_similarity()` (pure `math`, 384-dim),
  `ProductEmbedding` in `ai_assistant/models.py:431`.

## Dependency constraint (hard)

Platform is **numpy-free**. Phases 1–3 use only stdlib + Django ORM (Thompson =
`random.betavariate`, pure-Python; N candidates/request = microseconds). NO new deps.
LightGBM/sklearn/numpy only in the deferred Phase 4.

---

## Phase 1 — Real automated propensity engine (zero deps) — ✅ DONE

> Shipped: real bulk scorecard + `tasks.py` (nightly beat 3:30am + throttled
> post-order refresh) + canonical `orders.PAID_STATUSES`/`paid_order_items_qs()`
> + scheduled the never-scheduled `personalisation.recompute_copurchases` (2:30am).
> 7 new tests + 50-test dynamic_products/orders sweep green. **Deferred:**
> personalisation's `recompute_copurchases` still filters the invalid
> `'paid'/'completed'` statuses (a pre-existing under-count) — the fix drags in
> that file's pre-existing S110/SIM105 lint debt, so it's a separate follow-up,
> not Phase 1 scope.


**Files:**
- `plugins/installed/orders/services.py` — add canonical `PAID_STATUSES` tuple + a
  `paid_order_items_qs()`/`is_paid_status()` helper (single source of truth).
- `plugins/installed/personalisation/services.py` — repoint its wrong
  `('confirmed','paid','fulfilled','completed')` to the canonical orders helper
  (correctness fix — co-purchase currently under-counts).
- `plugins/installed/dynamic_products/services.py` — **rewrite**
  `calculate_grid_probabilities()` into a transparent, bulk-aggregated scorecard:
  - `sales` = recency-weighted units in paid orders (60d) — one `OrderItem` aggregate.
  - `demand` = `product_view` count (30d) — one `AnalyticsEvent` aggregate by `product_slug`.
  - `intent` = purchase/view rate (the strongest signal per research).
  - `trend` = last-14d vs prior-14d velocity ratio.
  - `inventory_factor` = real stock rollup (lazy inventory import, fail-soft; out=0, low=0.5).
  - `quality` = rating avg + `is_featured` + `is_on_sale` bumps.
  - Min-max normalize each component across the active catalog → weighted blend →
    × inventory_factor → `[0,1]`. Bulk `update_or_create`/`bulk_update` `DynamicGridItem`.
  - Fix the formula bug; document weights. Keep a `_score_components(...)` helper testable.
- `plugins/installed/dynamic_products/tasks.py` (**new**) — `@shared_task(name=
  'dynamic_products.recompute_probabilities')` → `calculate_grid_probabilities()`;
  a throttled variant for event-driven refresh.
- `plugins/installed/dynamic_products/plugin.py` — `register_celery_tasks(...tasks)`;
  `register_celery_beat('dynamic_products:recompute', {'task':..., 'schedule': crontab
  nightly})`; subscribe `ORDER_PLACED` (+ maybe `PRODUCT_VIEWED`) → enqueue a
  **throttled** recompute (Redis/cache guard so an order burst can't thrash).
- `plugins/installed/personalisation/plugin.py` — add the **missing** beat entry for
  `personalisation.recompute_copurchases` (nightly) so `CoPurchaseScore` refreshes.
- `plugins/installed/dynamic_products/tests/test_dynamic_grid.py` — replace the
  mock-attr tests with **real** ones: seed paid orders + analytics view events, run
  the recompute, assert a product with real sales+views+conversion scores higher than
  a cold one; assert out-of-stock → ~0; assert task/beat registered; assert paid-order
  helper correctness.

**Verify:** `DATABASE_URL='sqlite:///:memory:' python manage.py test
plugins.installed.dynamic_products plugins.installed.personalisation
plugins.installed.orders` green; `manage.py check`; ruff. Behaviour: probability_grid
now orders by a data-driven score; nightly + event refresh wired.

## Phase 2 — Self-optimizing per-visitor reranker (zero deps) — ✅ DONE

> Shipped: `BanditArm` (per product×segment Beta posterior) + migrations;
> `segments.py` (PII-free device×daypart×auth); `reranker.py` (pure-Python
> `random.betavariate` Thompson draw blended 50/50 with the Phase-1 propensity,
> + exploration floor + per-category diversity cap + cold-start uniform prior);
> a new `autopilot` strategy; `rebuild_bandit_posteriors` nightly beat (4:00am)
> that learns from product-view engagement bucketed by segment (views in
> converting sessions score higher). 10 tests; 30-test dynamic_products sweep
> green. **Honest limitation:** reward is view→session-conversion association, not
> counterfactual impression→purchase attribution (that needs the Phase-3
> visitor-id-on-order fix + Phase-4 SNIPS rigor) — documented in the code.


**Files:**
- `dynamic_products/models.py` — `BanditArm(product, segment, alpha, beta, impressions,
  ... )` (Beta-Bernoulli posterior per product×segment); `RecImpression(request_id,
  segment, item_ids JSON, propensities JSON, surface, created_at)` for the label loop.
- `dynamic_products/segments.py` (**new**) — `segment_for(request)` from anonymous
  session features (first-click category, device, referrer bucket, hour) → small
  fixed segment id (semi-personalized; ~dozens, not per-user). PII-free, consent-aware.
- `dynamic_products/reranker.py` (**new**) — `thompson_rerank(products, segment, *,
  exploration_floor, diversity_cap)`: draw `random.betavariate(α,β)` per arm, blend
  with the Phase-1 propensity score, apply exploration floor + per-category MMR
  diversity cap + cold-start pessimistic prior + new-product impression budget.
- `dynamic_products/services.py` — `probability_grid` (and a new `autopilot` strategy)
  route through the reranker; `_for_you` optionally blended.
- `dynamic_products/plugin.py` — subscribe `PRODUCT_LIST_REORDER` (pri > personalisation
  so it composes) to rerank; log a `RecImpression`; subscribe `ORDER_PLACED`/`PRODUCT_VIEWED`/
  cart → reward updates (value-weighted: purchase≫cart≫view) into `BanditArm`.
- `dynamic_products/tasks.py` — nightly `rebuild_bandit_posteriors` from analytics
  events joined to impressions (`request_id`); guardrail monitor + Redis kill-switch.
- Tests: bandit converges to the higher-reward arm; exploration floor honored; diversity
  cap caps per-category; cold-start arm explored; reward mapping correct; disable-safe.

## Phase 3 — AI merchandiser autopilot (LLM offline, human checkpoint) — ✅ DONE

> Shipped: `MerchandisingProposal` review-queue model + migration; `autopilot.py`
> (`ensure_default_blocks` zero-config provisioning; `generate_proposals` —
> data-driven proposals from live blocks / high-propensity products /
> `experiments.results_for` winners, with an optional bounded **offline** LLM
> rewrite of titles+rationales via the shared provider, fail-soft; `apply_proposal`
> / `dismiss_proposal` — low-risk actions only, audited via `core.audit`); a
> nightly `generate_merchandising_proposals` beat (5:00am); a dashboard review
> page (`/dashboard/dynamic-products/proposals/`) with Approve/Dismiss + nav entry.
> 11 tests; full 41-test dynamic_products sweep green. Migration 0005.
> **Scope notes:** the "human checkpoint" is the Approve click (nothing
> auto-applies) — heavier `core/safety.py` gating isn't needed because the only
> apply actions (provision/enable a block, feature products) are non-destructive;
> ADR 0029 respected (the LLM is a bounded text call, not a new agent class). The
> visitor-id-on-order attribution fix (for counterfactual bandit rewards) remains
> a follow-up, as does Phase 4 (LightGBM).


**Files:**
- `dynamic_products/autopilot.py` (**new**) — a nightly **Linda Worker** run (existing
  agent layer — NEVER a new agent class; ADR 0029) that reads KPIs + segment/bandit
  stats + probability distribution and **proposes** (JSON): default `DynamicBlock`s to
  auto-provision per slot, per-product rec-reasons ("Trending in Fiction"), auto-named
  segments, and the winning strategy per slot (consuming `experiments.results_for`).
- `dynamic_products/models.py` — `MerchandisingProposal(kind, payload JSON, status
  [proposed/approved/rejected/auto], created_at, reviewed_by)` — the review queue.
- Surface via the **ADR 0028 ops-inbox** + `core.audit`, gated by `core/safety.py`
  (propose-only; a human approves before anything applies; auto-apply only for
  low-risk, config-gated actions). Dashboard review page (plugin's own `DashboardPage`).
- Auto-provision: an "Autopilot" toggle → sensible default blocks so a store gets
  personalized merchandising with **zero manual config**.
- Anonymous attribution fix: stamp `visitor_id` onto the order at checkout so
  `experiments` can attribute `v:` visitors (feeds Phase-2/3 self-optimization).
- Tests: proposal generation is offline + cached (never per-request); review-queue
  approve/reject applies/discards; safety gate blocks auto-apply of risky actions;
  disable-safe.

## Cross-cutting

- **Plugin contract:** everything stays inside `plugins/installed/dynamic_products/`
  (+ the two surgical fixes to orders/personalisation services). New models → migration
  each phase (system check fails on prod boot otherwise). Both litmus tests must pass
  (delete-dir → gone; disable → surfaces vanish). Consent-gated, PII-free features.
- **ADR 0029:** the autopilot uses the ONE Linda Worker + a Skill/scopes — no new
  agent class.
- **Docs:** update `dynamic_products/plugin.py` docstring + this plan per phase; a
  Torsor ADR for the autopilot/self-optimization loop at the end.
- **Verify each phase:** scoped tests (sqlite mem) + `manage.py check` +
  `makemigrations --check` + ruff + boundary/pre-commit. Smoke live on "ship".

---

## Follow-up (2026-07-07): rename + more options — ✅ DONE

- **Renamed** the plugin `dynamic_products` → **`dynamics`** (module, Plugin.name,
  imports, URLs `/dashboard/dynamics/`, templates, tasks, logger). The Django app
  **label stays `dynamic_products`** so the live DB tables/migrations/content-types
  are untouched (zero data risk). Boot + 41-test suite verified.
- **+5 strategies:** trending, new_arrivals, best_sellers, on_sale, similar_price (PDP).
- **+block config (B2):** price_min/max, exclude_out_of_stock, exclude_purchased,
  pinned/excluded product-id lists (pins force-inject + resolve to real pks).
- **+display (B3):** layout (carousel/grid), columns, show_price, show_reason
  ("why" label from the strategy) — rendered by `_carousel.html`.
- **+autopilot controls (B4):** per-block exploration_rate / diversity_cap /
  segment_override (thread into the reranker), plus a plugin `auto_apply` settings
  toggle so the merchandiser can skip the review queue for low-risk actions.
- All settable in the block edit form; migrations 0006/0007; +18 tests (54 total).
