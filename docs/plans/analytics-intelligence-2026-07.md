# Analytics & Intelligence Buildout — Implementation Plan (2026-07)

> **For agentic workers:** execute task-by-task with the verify step after every task.
> Source spec: [`docs/analysis/platform_analysis_and_feature_proposals_2026.md`](../analysis/platform_analysis_and_feature_proposals_2026.md)
> **as corrected by the 2026-07-09 verification pass** (see "Corrections applied" below).

**Goal:** ship the report's seven proposals as compliant Morpheus plugins/modules, in four
deploy phases, without violating the plugin contract.

**Architecture:** every feature's analytics lives in the plugin that OWNS the data
(subscriptions computes MRR, post_purchase computes NPS, customers computes RFM).
Cross-plugin data moves only through `core.hooks` filters — the proven
`CHANNELS_OVERVIEW` / `BRAIN_SIGNALS` pull pattern — never through model imports.
Verified fact driving this: **nothing outside `analytics` writes `DailyMetric` today
and no rollup-contribution hook exists**, so the report's "other plugins add
DailyMetric dimensions" idea would create forbidden cross-plugin imports. We don't do it.

**Tech stack:** existing only — Django 6, Celery beat, the hooks bus, `DashboardPage` /
`register_urls` contributions, the dashboard design system (`.card`, `.morph-table`,
`.pill-*`, `.empty-state`, `{% sparkline %}`). **Zero new pip dependencies.**

## Corrections applied to the source report (do NOT re-introduce these errors)

1. **Proposal #7 is an EXTENSION, not a build.** `inventory/demand_forecast.py`
   (`forecast_all()`, reorder recommendations, lost-revenue ranking), the daily
   `inventory:run_stockout_forecast` beat, the `/dashboard/inventory/forecast/…`
   page (`stockout_forecast.html`), stockout alerts, and the
   `inventory.stockout_forecast` agent tool **already ship**. Phase 4 adds only the
   delta: overstock detection, exponential smoothing, a forecast sparkline, hooks.
2. **Web Vitals / RUM already exists** (`plugins/installed/seo/services/cwv.py`) —
   dropped from the gap list; nothing to build.
3. **Proposal #6 is per-install.** A self-hosted Morpheus has ONE merchant; "what %
   of merchants use X" is fleet telemetry we don't have. Build the per-install
   usage/health surface only.
4. **Scale numbers**: 104 plugins (not 85), 17 core subsystem dirs (not 35). Never
   hard-code counts — reference `MORPHEUS_DEFAULT_APPS`.
5. **Ad spend ingestion reuses existing channel report functions** — the channel
   plugins already fetch spend/ROAS (see `meta_commerce/app.py:97`,
   `google_shopping/app.py:96` contributing `spend` to `CHANNELS_OVERVIEW`).

## Global constraints (from CLAUDE.md — apply to every task)

- **Plugin contract:** new surfaces are contributions (`DashboardPage`,
  `contribute_settings_panel`, hooks, `register_urls`, `register_celery_beat`) —
  never edits to admin_dashboard/storefront/themes. Both litmus tests must pass:
  delete the plugin dir → no dangling refs; disable it → every surface disappears.
- **No cross-plugin model imports.** FK traversal is allowed only along an FK the
  plugin already declares via `requires` (e.g. `post_purchase.NPSResponse.order`).
- **Every new model ships its migration in the same commit** (prod boot fails otherwise).
- **Cross-type FK retargets = `RemoveField`+`AddField`** (sqlite hides Postgres crashes).
- **Test command:** `DATABASE_URL='sqlite:///:memory:' python manage.py test plugins.installed.<name>`
  (bare `manage.py test` hangs on the Docker `db` host).
- **After template edits:** compile every changed `.html` via `get_template()`
  (TemplateSyntaxError is invisible to `manage.py check` + untested views).
  Literal `{{ }}` in display text needs `{% verbatim %}`.
- **Dashboard UI:** use the design system (`.card`/`.card-padded`, `table.morph-table`,
  `.pill-*`, `.empty-state`, `.reveal-stagger`, `{% sparkline %}` for trends,
  icon+h1+description page header). No raw `bg-white`/`text-gray-*` (breaks dark mode).
- **Money:** `DailyMetric`-style `MoneyField` pairs; never feed `{% firstof %}` output
  to `|money`.
- **Each phase's merge to `main` = a production deploy** → bump `MORPHEUS_VERSION`
  + dated `docs/RELEASE_NOTES.md` entry in the same batch (ADR 0032).
- **New views ship the three permission-boundary tests** (anon blocked,
  non-staff blocked, staff allowed).
- **Docs ship with code:** new plugins get a `app.py` description; conventions/
  landmines discovered along the way go into `CLAUDE.md` in the same commit.

## Phase ordering & deploy gates

| Phase | Contents | Version bump |
|---|---|---|
| **0** | Fix the source report; funnel quick-win | PATCH |
| **1 (P0)** | #2 NPS dashboard · #1 Subscription analytics | MINOR |
| **2 (P1)** | #4 RFM segmentation · #3 Attribution + ROAS · #6 Feature adoption | MINOR |
| **3 (P2)** | #7 Forecasting extension · #5 Live commerce MVP | MINOR |

Each phase: all its tasks green → `ruff check` + `ruff format --check` + affected
test suites + template compile-check → ONE batched push (Coolify deploys `main`).
Verify the webhook actually started a build; manually trigger if not (see
memory/deploy_workflow).

---

## Phase 0 — Truth first (½ day)

### Task 0.1: Correct the source report

**Files:** Modify `docs/analysis/platform_analysis_and_feature_proposals_2026.md`

- [ ] §1.1: plugin count → "104 — see `MORPHEUS_DEFAULT_APPS`"; core subsystems → 17; hooks → "~52".
- [ ] §1.6: delete the "No Web Vitals / RUM tracking" row (exists: `seo/services/cwv.py`).
- [ ] Proposal #7: retitle "Extend the shipped inventory forecaster"; strike the
      already-shipped items (listed under "Corrections applied" above).
- [ ] Proposal #6: reframe use cases to per-install ("which features has *this store's*
      team used in 30/90 days"), drop fleet-% phrasing.
- [ ] Verify: re-read the diff; no other numeric claims left unqualified.
- [ ] Commit: `docs(analysis): correct platform report — shipped forecaster, existing RUM, real counts`

### Task 0.2: Render the funnel's computed-but-dropped data (the cheapest win in the report)

**Files:** Modify `plugins/installed/analytics/templates/analytics/funnel.html`
(view already passes `dropoffs` + `comparison` — `analytics/views.py:285-286`; zero template refs today)
**Test:** `plugins/installed/analytics/tests/` (extend the existing funnel view test)

- [ ] Read `services_cohorts.py:244` (`step_dropoffs`) and `:281` (`period_comparison`)
      to get the exact dict keys each returns.
- [ ] Add to `funnel.html` below the step table, using existing primitives:
      a "Biggest drop-offs" `.card` + `table.morph-table` (step → step, entered, lost,
      drop-off %), and a "vs previous period" `.card` row of KPI deltas
      (`.pill-success`/`.pill-danger` for direction).
- [ ] Extend the funnel view test: assert the response contains a drop-off percentage
      string and the comparison section heading.
- [ ] Verify: `DATABASE_URL='sqlite:///:memory:' python manage.py test plugins.installed.analytics`
      → green; compile `funnel.html` via `get_template()`.
- [ ] Commit: `feat(analytics): render funnel drop-offs + period comparison (data was computed, never shown)`

### Phase 0 deploy gate
- [ ] PATCH bump + `RELEASE_NOTES.md` entry → push → verify build → smoke `/dashboard/analytics/v2/funnel/` (302 anon).

---

## Phase 1 — P0: surface the money + satisfaction data you already collect

### Task 1.1: NPS dashboard (owner: `post_purchase` — its model, its page)

**Files:**
- Create `plugins/installed/post_purchase/analytics.py`
- Create `plugins/installed/post_purchase/templates/post_purchase/dashboard/nps.html`
- Create `plugins/installed/post_purchase/views_dashboard.py`
- Modify `plugins/installed/post_purchase/app.py` (add `DashboardPage`)
- Test  `plugins/installed/post_purchase/tests/test_nps_analytics.py`

**Interfaces (produces):**
```python
# plugins/installed/post_purchase/analytics.py
def nps_summary(days: int = 90) -> dict:
    """{'nps': int|None, 'promoters': int, 'passives': int, 'detractors': int,
        'responses': int, 'response_rate': float|None}"""
def nps_trend(weeks: int = 12) -> list[dict]:   # [{'week': date, 'nps': int, 'n': int}]
def nps_by_product(days: int = 90, limit: int = 20) -> list[dict]:
    # traverses NPSResponse.order → order.items → product (FK already declared via requires)
def recent_detractors(limit: int = 20) -> list[NPSResponse]  # score<=6, with comments first
```
Classification: 9–10 promoter, 7–8 passive, 0–6 detractor; NPS = %promoters − %detractors,
rounded int; `None` when `responses == 0`. Response rate = responses / NPS survey sends in
window (from the plugin's own send-log model; if absent, omit the KPI — do NOT guess).

- [ ] Write failing tests first: seeded `NPSResponse` rows → exact NPS math (e.g. 6 promoters,
      2 passives, 2 detractors → NPS 40); empty DB → `nps is None`; per-product attribution
      splits multi-item orders (each product on the order gets the response's score).
- [ ] Implement `analytics.py` (pure ORM aggregation on own model; no new tables).
- [ ] View `nps_dashboard` (`@staff_member_required`) + template: NPS headline KPI card,
      12-week `{% sparkline %}` trend, promoter/passive/detractor distribution
      (3 `.pill-*` stat tiles — no pie-chart dependency), product table
      (`table.morph-table`: product, n, NPS, promoter %), detractor-comments feed
      (`.card` list, newest first), `.empty-state` when no responses.
- [ ] Register: `DashboardPage(label='NPS', slug='nps', view='…views_dashboard.nps_dashboard',
      icon='smile', section='analytics', nav='main', order=60)`.
- [ ] Permission-boundary tests (anon 302, non-staff blocked, staff 200 + 'NPS' in body).
- [ ] Verify: `…manage.py test plugins.installed.post_purchase` green; disable-test: toggle
      post_purchase off → nav entry + page gone.
- [ ] Commit: `feat(post_purchase): NPS analytics dashboard — the scores were collected, never aggregated`

### Task 1.2: Subscription analytics (owner: `subscriptions`)

**Files:**
- Create `plugins/installed/subscriptions/analytics.py`
- Create `plugins/installed/subscriptions/templates/subscriptions/dashboard/analytics.html`
- Modify `plugins/installed/subscriptions/views.py` (or create `views_analytics.py`)
- Modify `plugins/installed/subscriptions/app.py` (add `DashboardPage`)
- Test  `plugins/installed/subscriptions/tests/test_analytics.py`

**Interfaces (produces):**
```python
# plugins/installed/subscriptions/analytics.py
MONTHLY_FACTOR = {'day': Decimal(30), 'week': Decimal(52) / 12, 'month': Decimal(1), 'year': Decimal(1) / 12}

def committed_mrr() -> Money:
    """Live: Σ over state='active' subs of plan.price * MONTHLY_FACTOR[plan.interval] / plan.interval_count."""
def mrr_trend(months: int = 12) -> list[dict]:
    """Recognized MRR per month from PAID SubscriptionInvoices: amount normalized by
    invoice period length (amount * 30 / (period_end-period_start).days), summed per month.
    Invoice-based → fully reconstructable, no snapshot model needed."""
def churn_rate(days: int = 30) -> dict:   # {'cancelled': int, 'active_at_start': int, 'rate': float|None}
def trial_funnel(days: int = 90) -> dict  # trials started / converted (reached started_at+plan.trial_days still active|active later) / cancelled in trial
def plan_breakdown() -> list[dict]        # per plan: active subs, committed MRR, trialing, cancelled_30d
```
**Documented approximations (put in the module docstring):** historical `paused`/`past_due`
states aren't event-sourced, so *committed*-MRR history is not reconstructable — that's why
the trend uses paid invoices (recognized MRR). Trial conversion infers from
`started_at + plan.trial_days` vs `cancelled_at` because state transitions aren't logged.

- [ ] Failing tests first: plan `$10/month` ×3 active + 1 trialing + 1 cancelled →
      `committed_mrr == $30`; yearly `$120` plan ×1 active → adds `$10`; invoice of `$30`
      over a 30-day period → that month's recognized MRR `$30`; churn with
      2 cancels / 20 active → 10%; empty DB → zeros/None, page still 200.
- [ ] Implement `analytics.py`.
- [ ] Dashboard page: KPI row (`.reveal-stagger`): Committed MRR, Active subscribers,
      Churn 30d, Trial→paid %; MRR `{% sparkline %}` (12 mo recognized); plan-breakdown
      `table.morph-table`; trial funnel 3-stat strip; `.empty-state` when no plans.
- [ ] Register `DashboardPage(label='Subscription analytics', slug='analytics',
      section='analytics', nav='main', icon='repeat', order=55)`.
- [ ] Permission-boundary tests + disable-test.
- [ ] Verify: `…manage.py test plugins.installed.subscriptions` green; template compiles.
- [ ] Commit: `feat(subscriptions): MRR / churn / trial analytics dashboard`

### Phase 1 deploy gate
- [ ] MINOR bump + release-notes entry ("See your subscription revenue and customer
      satisfaction at a glance") → one push → verify build → smoke both routes (302 anon).

---

## Phase 2 — P1: segmentation, attribution, adoption

### Task 2.1: RFM segmentation + segment-change triggers (owner: `customers`)

**Files:**
- Create `plugins/installed/customers/rfm.py`
- Create `plugins/installed/customers/migrations/000X_customersegment.py`
- Modify `plugins/installed/customers/models.py` (add `CustomerSegment`)
- Modify `plugins/installed/customers/app.py` (beat task + `DashboardPage`)
- Create `plugins/installed/customers/tasks.py` (if absent)
- Create `plugins/installed/customers/templates/customers/dashboard/segments.html`
- Modify `core/hooks.py` (add `CUSTOMER_SEGMENT_CHANGED = 'customer.segment_changed'  # fire`)
- Test  `plugins/installed/customers/tests/test_rfm.py`

**Model:**
```python
class CustomerSegment(models.Model):
    customer = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='rfm_segment')
    r_score = models.PositiveSmallIntegerField()  # 1-5, quintile of last_order_at recency
    f_score = models.PositiveSmallIntegerField()  # 1-5, quintile of purchase_count
    m_score = models.PositiveSmallIntegerField()  # 1-5, quintile of lifetime_value
    segment = models.CharField(max_length=20, db_index=True)  # champions|loyal|potential|at_risk|lost|new
    computed_at = models.DateTimeField(auto_now=True)
```
Fields feed from `Customer.lifetime_value` / `purchase_count` / `last_order_at`
(verified present: `customers/models.py:57-67`). Classification map (explicit, tested):
champions R≥4∧F≥4∧M≥4 · loyal R≥3∧F≥3 · potential R≥3∧F<3 · at_risk R≤2∧F≥3 ·
lost R≤2∧F≤2 · new: first order <30d. Quintiles computed against the full customer
base per run (`percent_rank`-style ordering in Python; the base is small enough).

- [ ] Failing tests first: a seeded 10-customer distribution → exact segment assignments;
      re-run after mutating one customer → segment flips AND
      `CUSTOMER_SEGMENT_CHANGED` fires once with `{customer_id, old, new}`
      (assert via a test hook subscriber); customers with 0 orders → 'new'/excluded rule.
- [ ] Implement `rfm.py: recompute_all() -> {'changed': int, 'total': int}` —
      bulk fetch, score, `bulk_create/bulk_update`, fire the hook per change.
- [ ] Beat: `customers:recompute_rfm` nightly 04:30 (after orders settle, before merchandiser 05:00).
- [ ] Dashboard page `Segments` (section='customers'): segment distribution as
      `.reveal-stagger` stat tiles (count + revenue share per segment), per-segment
      `table.morph-table` (top customers, LTV, last order), 30-day migration summary
      ("12 became at-risk · 3 recovered") — computed by diffing `computed_at` batches
      is NOT possible without history; instead log migrations to a small
      `SegmentMigration(customer, old, new, day)` append-only table written by the hook
      subscriber inside the same plugin. Include that model in the same migration.
- [ ] Workflows integration (zero code): document in the page's help text that
      `customer.segment_changed` is triggerable from the workflows plugin (it consumes
      arbitrary hook events already).
- [ ] Permission-boundary + disable tests.
- [ ] Verify: `…manage.py test plugins.installed.customers` green; `makemigrations --check` clean.
- [ ] Commit: `feat(customers): RFM segmentation — nightly scoring, segments dashboard, segment-change hook`

### Task 2.2: Ad-spend ingestion + multi-touch attribution + ROAS (owner: `analytics`)

**Files:**
- Modify `core/hooks.py` (add `ANALYTICS_AD_SPEND = 'analytics.collect_ad_spend'  # filter`)
- Create `plugins/installed/analytics/models_adspend.py` → `AdSpendSnapshot(day, channel, spend Money, source_meta JSON)` + migration (unique `(day, channel)`)
- Create `plugins/installed/analytics/services_attribution.py`
- Modify `plugins/installed/analytics/tasks.py` (nightly `collect_ad_spend` + `attribute_revenue`)
- Create `plugins/installed/analytics/templates/analytics/attribution.html` + view + URL (`attribution/` in `urls_dashboard.py`)
- Modify 2 channel plugins first (`meta_commerce`, `google_shopping`) to subscribe to the
  filter reusing their existing spend-report functions (the same ones feeding
  `CHANNELS_OVERVIEW` — `app.py:96-97` in each); remaining channels follow the pattern later.
- Test `plugins/installed/analytics/tests/test_attribution.py`

**Attribution core (pure function, exhaustively tested):**
```python
MODELS = ('last_touch', 'first_touch', 'linear', 'time_decay', 'position_based')
def attribute(journey: list[Touch], revenue: Decimal, model: str) -> dict[str, Decimal]:
    """Touch = (channel, timestamp). Rules:
    last/first: 100% to that touch. linear: revenue/n each.
    time_decay: weight 2^(-days_before_purchase/7), normalized.
    position_based: 40% first, 40% last, 20% split across middles (100% if single touch)."""
```
Journeys built nightly from `AnalyticsEvent` per purchaser (session/customer chain,
UTM-source touches, 30-day lookback). Persist per-model per-channel daily revenue to
`DailyMetric` with `metric='attribution', dimension=f'{model}:{channel}'` —
analytics owns `DailyMetric`, so this is legal here.

- [ ] Failing tests first: fixed journey (meta d-10 → google d-3 → email d-0, $100) →
      exact per-model splits (linear 33.33/33.33/33.33; time_decay weights 2^-10/7 …;
      position 40/20/40); single-touch → 100% all models; ROAS = attributed revenue / spend,
      `None` when spend 0.
- [ ] Implement `services_attribution.py` + the two nightly tasks (spend filter fire → upsert
      snapshots; journey build → DailyMetric rows).
- [ ] Subscribe `meta_commerce` + `google_shopping` to `ANALYTICS_AD_SPEND` via
      `self.register_hook` in `ready()` (disable-gated for free by the bus).
- [ ] Dashboard page: model picker (GET param), per-channel horizontal bar (CSS bars —
      no chart lib), ROAS `table.morph-table` (channel, spend, attributed revenue, ROAS,
      trend `{% sparkline %}`), model-comparison strip, `.empty-state` explaining the
      nightly job when no data.
- [ ] Permission-boundary tests; migration on real Postgres in CI (`migrations` job).
- [ ] Verify: `…manage.py test plugins.installed.analytics plugins.installed.meta_commerce plugins.installed.google_shopping` green.
- [ ] Commit: `feat(analytics): multi-touch attribution + ROAS — ad spend via ANALYTICS_AD_SPEND filter`

### Task 2.3: Feature adoption & install health (new plugin `feature_adoption`, per-install)

**Files:** Create `plugins/installed/feature_adoption/` — `apps.py`, `app.py`,
`models.py` + migration, `tracking.py`, `tasks.py`, `views.py`,
`templates/feature_adoption/dashboard.html`, `tests/`. Register in `MORPHEUS_DEFAULT_APPS`.
(Use the `plugin-skeleton` skill for scaffolding.)

**Model (aggregates only — no per-event rows, no PII):**
```python
class FeatureUsageDay(models.Model):
    day = models.DateField(db_index=True)
    plugin = models.CharField(max_length=80)     # owning plugin, from the registry
    surface = models.CharField(max_length=20)    # 'dashboard' | 'agent_tool' | 'settings'
    count = models.PositiveIntegerField(default=0)
    # unique_together: (day, plugin, surface)
```
**Instrumentation (contributions only, zero core edits):**
- dashboard hits: `register_context_processor` → on `/dashboard/…` requests, resolve the
  owning plugin from the path prefix and `cache.incr` a per-day counter (fail-soft, ~0 cost);
  an hourly beat flushes counters to `FeatureUsageDay`.
- agent tools: subscribe to the existing `AgentEvents.TOOL_CALLING` filter → count by
  tool-name prefix.
- settings saves: subscribe to the existing settings-saved hook if present; else count the
  settings-panel POST path via the same context-processor path map (verify which exists first).

- [ ] Failing tests: two dashboard hits + flush → one row `count=2`; unknown path → no row;
      health score math (below) on fixtures.
- [ ] Health score: `install_health() -> {'score': 0-100, 'components': {...}}` =
      breadth (plugins used 30d / plugins enabled, 40pts) + agent usage (tool calls 30d
      capped, 30pts) + freshness (days since last dashboard visit, 30pts). Pure + tested.
- [ ] Dashboard page (admin-only): adoption matrix `table.morph-table`
      (plugin × used-7/30/90d × trend sparkline), "never used in 90d" list (deprecation
      candidates), health-score KPI tile — also contributed to the home page via the
      existing `DASHBOARD_KPIS` filter (disable-safe automatically).
- [ ] Permission-boundary + disable + delete litmus tests.
- [ ] Verify: `…manage.py test plugins.installed.feature_adoption` green; boundary guard clean.
- [ ] Commit: `feat(feature_adoption): per-install feature usage + install health (new plugin)`

### Phase 2 deploy gate
- [ ] MINOR bump + release notes → one push → verify build → smoke the three new routes.

---

## Phase 3 — P2: forecasting delta + live commerce MVP

### Task 3.1: Extend the shipped inventory forecaster (owner: `inventory`)

**Files:** Modify `demand_forecast.py`, `views.py`, `agent_tools.py`, `app.py`,
`templates/inventory/dashboard/stockout_forecast.html`; `core/hooks.py`
(add `INVENTORY_OVERSTOCK_DETECTED = 'inventory.overstock_detected'  # fire`);
tests in `tests/test_forecasting_extensions.py`.

- [ ] **Overstock detection** (failing test first): extend `ForecastRow` with
      `days_of_supply` + `overstocked: bool` (days_of_supply > 90 AND velocity below
      catalog-median); `forecast_all()` gains `include_overstock=True`. Fire the new hook
      per newly-overstocked SKU from the existing daily beat (dedup'd like stockout alerts).
- [ ] **Exponential smoothing** (failing test first): replace the flat window-average
      velocity with EWMA (α=0.3) over daily `StockMovement` outflows; document that
      seasonality beyond EWMA is out of scope this round (matches report's own
      "simple exponential smoothing" ask).
- [ ] **Page**: add an "Overstocked" `table.morph-table` section (product, days of supply,
      suggested action "promote/discount") + a per-row demand `{% sparkline %}`
      (last 30d outflow series) to `stockout_forecast.html`.
- [ ] **Agent tool**: extend `inventory.stockout_forecast` output with `overstock` rows so
      Linda answers "what's overstocked?" too.
- [ ] Verify: `…manage.py test plugins.installed.inventory` green; template compiles.
- [ ] Commit: `feat(inventory): overstock detection + EWMA velocity in the shipped forecaster`

### Task 3.2: Live commerce MVP (new plugin `live_commerce`)

Scope discipline: **MVP = scheduled event + embedded stream + pinned buyable products +
live stats.** Own WebRTC, chat overlays, and auto-VOD re-encoding are explicitly out
of scope this round (the report's own stretch items).

**Files:** Create `plugins/installed/live_commerce/` — `apps.py`, `app.py`,
`models.py` + migration, `views.py` (storefront + dashboard), `urls.py`,
`templates/live_commerce/` (`event.html` storefront, `dashboard/index.html`,
`dashboard/form.html`, `blocks/upcoming_teaser.html`), `tests/`.
Register in `MORPHEUS_DEFAULT_APPS`. `requires = ['catalog', 'orders']`.

**Models:**
```python
class LiveEvent(models.Model):
    title, slug (unique), description
    scheduled_start, scheduled_end = DateTimeField()
    status = CharField(choices=['scheduled','live','ended'], default='scheduled', db_index=True)
    embed_url = URLField(help_text='YouTube Live / any HLS embed URL')
    recording_url = URLField(blank=True)  # set after the event → page becomes a replay
class LiveEventProduct(models.Model):
    event FK, product FK ('catalog.Product', declared via requires), sort_order, pinned_at
```
**Surfaces (all contributions):**
- storefront `register_urls`: `/live/` (upcoming + past list) and `/live/<slug>/` —
  event page: embedded player + product rail (reuses the storefront product-card
  include) + "LIVE" state handling; replay state when `recording_url` set.
- `StorefrontBlock(slot='home_below_grid', template='live_commerce/blocks/upcoming_teaser.html')` —
  self-hides when no scheduled/live event.
- dashboard: event CRUD (list/form with the option-fieldset pattern from dynamics),
  a "go live / end" action pair, and a during-event stats strip.
- hooks: fire `LIVE_EVENT_STARTED` / `LIVE_EVENT_ENDED` (add both to `core/hooks.py`);
  analytics ingests page views through its existing beacon — **do not** touch analytics'
  `_ALLOWED_KINDS`; event-page conversion is measured by UTM (`?utm_source=live&utm_campaign=<slug>`
  auto-appended to product links) flowing through the existing attribution pipeline (Task 2.2).

- [ ] Failing tests first: model states; storefront page 200 + shows pinned products in
      order; teaser hidden with no events; dashboard CRUD permission-boundary tests;
      disable test (storefront URLs 404, teaser gone, nav gone).
- [ ] Implement models + migration → storefront views/templates → dashboard CRUD →
      teaser block → hooks.
- [ ] Verify: `…manage.py test plugins.installed.live_commerce` green; both litmus tests;
      template compile sweep.
- [ ] Commit: `feat(live_commerce): live shopping events MVP — scheduled events, embedded stream, pinned products`

### Phase 3 deploy gate
- [ ] MINOR bump + release notes → push → verify build → smoke `/live/` + forecast page.

---

## What this plan deliberately does NOT do

- No `DailyMetric` writes from outside analytics, no metric-contribution mega-filter —
  each owner computes from its own models (cheap at merchant scale, zero new coupling).
- No new pip dependencies (no charting lib — sparklines + CSS bars; no stats lib — EWMA
  and quintiles are stdlib math).
- No Bayesian experiments, DPP/sustainability, POS, or retail-media (report's own
  out-of-scope list).
- No fleet telemetry in feature_adoption (single-install product).

## Success criteria (whole plan)

1. Seven dashboards/routes live and staff-gated; every one passes the disable litmus test.
2. All new math ships with exact-value unit tests (NPS, MRR normalization, churn,
   attribution splits, RFM quintiles, EWMA, health score).
3. `scripts/check_core_boundary.py` baseline does not grow (zero new core→plugin imports).
4. CI green including the real-Postgres `migrations` job for the 4 new migrations
   (CustomerSegment+SegmentMigration, AdSpendSnapshot, FeatureUsageDay, LiveEvent*).
5. Three deploys, three version bumps, three release-notes entries (ADR 0032).
