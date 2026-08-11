# Analytics Trust Foundation (Slice 1) — Design

**Date:** 2026-07-05 · **Status:** approved (foundation-first; slices 2–3 follow)
**Owner plugin:** `plugins/installed/analytics/` (all changes stay inside the plugin
contract: models+migrations in-plugin, cross-plugin via `core.hooks`, surfaces via
contributions).

## Context

Deep research (4 lenses, 2025–2026 sources) + a 2-part codebase audit found the
analytics plugin is a competent first-party *capture* engine (`AnalyticsSession`,
`AnalyticsEvent`, `DailyMetric` rollups, cohorts, real-time, AI-traffic
attribution) with a partly **broken and untrustworthy** measurement layer. Three
defects were verified in code:

1. **Funnel page 500s** — `services_cohorts.py:step_dropoffs` reads
   `prev['name']`/`cur['name']` but `services.py:funnel_for` returns
   `{'step', 'sessions'}` → `KeyError('name')` whenever ≥2 steps have data.
2. **`checkouts_started` is always 0** — `core/hooks.py:388` defines
   `BEGIN_CHECKOUT = 'checkout.started'` (and checkout views fire it), but
   `services.py:roll_daily` (~L296) counts `name='checkout.start'`.
3. **Conversion rate is inflated** — mid-funnel events (`product_view`,
   `search`, `cart`) are client-beacon-only (ad-blockers/no-JS silently drop
   them) while `order.placed` lands server-side; `PRODUCT_VIEWED` /
   `SEARCH_PERFORMED` hooks exist in `core/hooks.py` and analytics subscribes,
   but **no view fires them**.

Plus trust gaps: the beacon accepts client-forgeable money/auth kinds
(`purchase`, `checkout`, `signup`, `login` in `views.py:_ALLOWED_KINDS`);
`order.placed` + `payment.captured` both map to `kind='purchase'` (latent
double-count); non-consented visitors mint a fresh `AnalyticsSession` row per
request (`services.py:get_or_create_session` generates a cookie_id but only
persists the cookie when consented — sessions inflate); and the plugin
contributes **nothing** to the dashboard home while its strongest report
(Cohorts) has no nav entry.

**Goal of slice 1:** make the numbers *correct and trustworthy*, make the
plugin *visible*, and land the first proactive-intelligence capability
(anomaly alerts). Slice 2 (Linda-as-analyst: governed metrics registry +
`analytics.query` NL tool + narrative insights) builds on this clean data.
Slice 3: RFM/CLV/churn + multi-touch attribution.

## Non-goals (this slice)

- No NL-query/insight-narrative layer (slice 2).
- No RFM/CLV/churn models, no multi-touch attribution (slice 3).
- No session replay, no consolidation of the duplicate
  `admin_dashboard/views_split/analytics.py` surface (queued; separate change).
- No real-time re-architecture (Redis/SSE) — the polling page stays.

## Design — 8 changes

### 1. Fix the funnel 500
`services_cohorts.py:step_dropoffs`: `prev['name']`→`prev['step']`,
`cur['name']`→`cur['step']`. Add a view-level regression test that GETs the
funnel dashboard with ≥2 steps of event data and asserts 200 + drop-off rows
render (`views.py:funnel_view`).

### 2. Server-side funnel emitters
Fire the already-defined hooks from the owning views (they import nothing from
analytics — `core.hooks` only, per contract):
- `MorpheusEvents.PRODUCT_VIEWED` from the storefront PDP view
  (`storefront/views/catalog.py:product_detail`), kwargs per the hook's
  contract (`product=`, `customer=`), fail-soft (`try/except` + log).
- `MorpheusEvents.SEARCH_PERFORMED` from the storefront search view
  (kwargs: `query=`, `results_count=`).
- Analytics already subscribes to both (`app.py:ready`); its `_on_event`
  handler records them with a session, so funnels stop depending on the
  ad-blockable beacon. The beacon keeps firing the same events client-side;
  the existing `idempotency_key` pathway dedupes where both land — verify and,
  if the beacon's key derivation can't dedupe against server events, prefer
  the server event and drop the beacon kind (see change 4).

### 3. Reconcile the checkout event name
Single canonical name: `checkout.started` (the `core/hooks.py` constant).
Update `services.py:roll_daily` to count `name='checkout.started'`, and the
default funnel steps anywhere `checkout.start` appears (grep the plugin).
Backfill note: historical rows named `checkout.start` (if any exist — the
mismatch means the hook-side name was recorded) — verify which name actually
landed in `AnalyticsEvent` and align to *that* reality; do not rewrite rows.

### 4. Lock down the beacon
`views.py:_ALLOWED_KINDS`: remove `purchase`, `checkout`, `signup`, `login`
(money/auth truth comes from server hooks only — this also removes the
`order.placed`+`payment.captured` double-count exposure from the client side;
additionally map only `order.placed` to `kind='purchase'` in the server
`_kind_for`, with `payment.captured` recorded under a non-purchase kind).
Add a simple per-IP rate limit on `track_beacon` (cache-based counter, e.g.
120 events/min/IP → 429). Update `tracker.html` to stop sending the removed
kinds.

### 5. Consent-gate ingestion
`services.py:get_or_create_session`: when not consented, do **not** create an
`AnalyticsSession` row per request — either reuse a request-scoped transient
session (no DB row, events recorded session-less) or skip visitor-level
capture entirely, keeping only aggregate counters; pick the simpler:
**non-consented → `session=None` events with no cookie**, so `sessions`
reflects consented visitors only. `middleware.py` + `track_beacon` route
through the same choke point. Server-side *commerce* events (orders) are
first-party operational data and continue to record (with `customer` when
known, no analytics cookie).

### 6. Dashboard-home presence
In `app.py:ready()`, register filters:
- `MorpheusEvents.DASHBOARD_KPIS` (`'dashboard.kpis'`) — append KPI dicts
  (sessions today, conversion rate, AI-referred revenue) computed from
  `DailyMetric` (cheap indexed reads, no event scans).
- `MorpheusEvents.ACTIVITY_FEED` (`'dashboard.activity_feed'`) — recent
  notable events (first purchase from a new channel, anomaly alerts from
  change 8).
Disable-safe for free via the hook bus's active-state gating.

### 7. Cohorts in nav + derived KPI rollups
- `app.py:contribute_dashboard_pages`: add
  `DashboardPage(label='Cohorts', slug='cohorts', view='…views.cohort_view', icon='users', section='analytics', order=40)`.
- `services.py:roll_daily`: upsert derived metrics `conversion_rate`
  (purchases/sessions), `aov` (revenue/orders), `cart_abandonment`
  (1 − checkouts/cart_adds) into `DailyMetric` so history survives the 90-day
  raw-event trim. Ratios stored as percents in the existing `value_money`
  decimal (e.g. `2.40` = 2.4%) — **zero migration**; the slice adds no model
  changes.

### 8. Anomaly alert v1
New `services_anomaly.py`: for key metrics (`revenue`, `orders`, `sessions`,
`conversion_rate`), compare today's `DailyMetric` against a day-of-week
baseline (mean ± MAD/z-score over the trailing 8 same-weekdays); beyond
threshold → fire a `core.hooks` notification event (consumed by the
notifications plugin + surfaced via ACTIVITY_FEED). Nightly Celery beat in
`tasks.py` (registered via `register_celery_beat`). Conservative defaults
(z ≥ 3, min 7 days history, max 1 alert/metric/day) — no ML, no new deps.

## Verification

- Unit: funnel drop-off keys; roll_daily counts `checkout.started`; beacon
  rejects removed kinds (403/ignored) + rate limit 429; consent path creates
  zero sessions for non-consented requests; anomaly detector fires on a
  seeded spike and stays quiet on flat data.
- View: funnel page GET-200 with data; cohorts nav renders; dashboard home
  shows the analytics KPIs (and hides them when the plugin is disabled —
  disable test).
- E2E (local runserver): browse PDP + search with JS disabled (curl) →
  events still land server-side; place the smoke order → exactly one
  purchase event; conversion_rate/AOV appear in DailyMetric after
  `roll_daily`.
- Suites: `DATABASE_URL='sqlite:///:memory:' python manage.py test plugins.installed.analytics plugins.installed.storefront` green; ruff clean.

## Risks / notes

- **Event-volume growth**: server-side PDP/search events add rows for all
  human traffic. Mitigated by the existing 90-day trim + bot filtering; the
  consent change *reduces* session rows.
- **Beacon dedup vs server events**: if double-recording of `product_view`
  is detected in E2E, drop the beacon kind entirely (server wins) rather
  than build fancy dedup.
- **Historic continuity**: `checkouts_started` was 0 before; dashboards will
  show a step increase. Same for sessions (decrease after consent gating).
  Called out in the commit message; not a bug.
- Zero migrations in this slice — nothing for the Postgres migration gate to
  catch.
