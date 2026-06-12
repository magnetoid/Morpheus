# Predictive Stockout Alerts — Design Spec

**Date:** 2026-06-12
**Status:** Draft for review
**Owner:** inventory plugin
**Source:** `docs/analysis/comprehensive_ecommerce_feature_research_2026.md` (Domain 2, HIGH priority)

---

## 1. Summary

Wire up the inventory plugin's **already-implemented but dead** demand-forecast engine
into a stateful, merchant-facing **Predictive Stockout Alerts** feature: a daily job
that detects SKUs projected to run out within a lead-time window, alerts staff once per
stockout episode, surfaces the at-risk list on a dedicated dashboard page, and exposes
the forecast to Linda.

This is an **enhancement to the `inventory` plugin**, not a new app — the engine reads
`StockMovement`/`StockLevel`, which `inventory` owns; a separate plugin would have to
import those models, violating the no-cross-plugin-models rule.

## 2. Problem & current state

`plugins/installed/inventory/demand_forecast.py` already computes, per variant:
- rolling daily velocity from `StockMovement` where `movement_type='sale'`,
- `days_until_stockout = available / velocity`,
- `reorder_recommended` (days_until < threshold), and a `suggested_reorder_qty`.

Verified facts:
- `forecast_all(*, window_days=28, threshold_days=14, reorder_multiplier=2.0) -> list[ForecastRow]`
- `ForecastRow(variant_id, variant_label, available, daily_velocity, days_until_stockout, reorder_recommended, suggested_reorder_qty, sold_in_window, window_days)`
- `_severity_for(row) -> int` (30/45/60/75/90 by urgency)

**But it is orphaned**: `forecast_all()` / `emit_reorder_signals()` are never called, never
scheduled, never surfaced, and have **zero tests**. The merchant gets no benefit today.
The existing `inventory.low_stock_report` agent tool and home panel are **static-threshold
only** (`available <= reorder_point`) — they do not use velocity, so they miss a fast-moving
SKU that's still above its reorder point but will sell out in 3 days.

## 3. Goals / non-goals

**Goals**
- Run the forecast on a daily schedule.
- Alert staff **once per stockout episode** (no daily nagging) — requires alert state.
- Give merchants a dedicated, contract-clean page to see at-risk SKUs.
- Give Linda a predictive tool (`inventory.stockout_forecast`).
- Add the missing test coverage for the engine + the new layer.

**Non-goals (YAGNI — deferred)**
- A settings UI to tune window/threshold/lead-time (use the engine defaults; operators can
  override the beat cadence via Django settings).
- ML forecasting (the deterministic velocity model is intentionally chosen; see the module docstring).
- A dedicated `demand` self-improvement signal source (the existing `emit_reorder_signals`
  stays as-is, untouched).
- Auto-creating purchase orders / reorder automation.

## 4. Architecture

Six pieces, all inside `plugins/installed/inventory/`:

### 4.1 State model — `StockoutAlert` (`models.py` + migration)
The dedup/lifecycle anchor. `notify_all_staff` has **no built-in dedup**, so state lives here.

```
class StockoutAlert(models.Model):
    id              = UUIDField(pk, default=uuid4, editable=False)
    variant         = FK('catalog.ProductVariant', on_delete=CASCADE, related_name='stockout_alerts')
    status          = CharField(choices=[('open','Open'),('resolved','Resolved')], default='open', db_index=True)
    days_of_cover   = FloatField(null=True)   # snapshot at open/last-sync; None = no velocity
    daily_velocity  = FloatField(default=0)
    suggested_reorder_qty = IntegerField(default=0)
    opened_at       = DateTimeField(auto_now_add=True)
    last_seen_at    = DateTimeField(auto_now=True)   # refreshed each sync while still at-risk
    resolved_at     = DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['days_of_cover']
        constraints = [UniqueConstraint(fields=['variant'], condition=Q(status='open'),
                                        name='uniq_open_stockout_alert_per_variant')]
        indexes = [Index(fields=['status', 'days_of_cover'])]
```

The partial unique constraint guarantees **at most one OPEN alert per variant** — the
structural dedup. Conventions verified against existing inventory models (UUID PK, Meta
indexes, `catalog.ProductVariant` relation).

### 4.2 Reconciler — `sync_stockout_alerts()` (extend `demand_forecast.py`)
Pure, 0-arg-friendly; the heart of the dedup logic.

```
def sync_stockout_alerts(*, window_days=DEFAULT_WINDOW_DAYS,
                         threshold_days=DEFAULT_REORDER_THRESHOLD_DAYS) -> dict:
    rows = forecast_all(window_days=window_days, threshold_days=threshold_days)
    at_risk = {r.variant_id: r for r in rows if r.reorder_recommended}
    open_alerts = {a.variant_id: a for a in StockoutAlert.objects.filter(status='open')}

    opened, refreshed, resolved = [], [], []
    # open new / refresh existing
    for vid, row in at_risk.items():
        if vid in open_alerts:
            update snapshot fields + last_seen_at  -> refreshed
        else:
            create StockoutAlert(open, snapshot)   -> opened
    # resolve recovered
    for vid, alert in open_alerts.items():
        if vid not in at_risk:
            alert.status='resolved'; alert.resolved_at=now()  -> resolved
    return {'opened': opened, 'refreshed': len(refreshed), 'resolved': len(resolved)}
```

Transition semantics: alert opens on `not-at-risk → at-risk`; resolves on `at-risk →
recovered` (restock raises `available`, or velocity drops). One alert per episode.

### 4.3 Daily beat task — `inventory.run_stockout_forecast` (`tasks.py` + `plugin.py`)
Verified beat mechanism: `@app.task(name=...)` in `tasks.py`, registered in `plugin.ready()`
via `self.register_celery_beat('inventory:run_stockout_forecast', {'task': 'inventory.run_stockout_forecast', 'schedule': crontab(hour=6, minute=0)})` (daily 06:00 UTC; `setdefault` lets operators override).

```
@app.task(name='inventory.run_stockout_forecast', ignore_result=True, time_limit=120, soft_time_limit=90)
def run_stockout_forecast() -> dict:
    result = sync_stockout_alerts()
    newly = result['opened']
    if newly:
        # fail-soft import (notifications_center may be absent)
        notify_all_staff(
            kind='inventory.stockout_forecast',
            title=f'{len(newly)} SKU(s) projected to stock out soon',
            body='\n'.join(f'{a.variant} — ~{a.days_of_cover:.0f}d of cover, reorder {a.suggested_reorder_qty}' for a in newly[:10]),
            action_url='/dashboard/apps/inventory/stockout-forecast/',
            icon='alert-triangle',
        )
    return {'opened': len(newly), 'resolved': result['resolved']}
```

Notifications fire **only for `opened`**, never `refreshed` — that is the no-nagging guarantee.
`notify_all_staff(*, kind, title, body='', action_url='', icon='bell') -> int` (keyword-only, fail-soft, verified).

### 4.4 Dashboard visibility — dedicated `DashboardPage` (contract-clean)
**Refinement from the original "home panel" idea:** verification showed `DASHBOARD_HOME_PANELS`
panel keys map to hardcoded sections in `admin_dashboard/home.html`; adding a *new* panel there
would edit a sibling plugin (contract violation). Instead, `inventory` contributes a page it
**fully owns**:

```
DashboardPage(label='Stockout Forecast', slug='stockout-forecast',
              view='plugins.installed.inventory.views.stockout_forecast_view',
              icon='trending-down', section='catalog', nav='main')
```

`stockout_forecast_view` (new, in `inventory/views.py`) renders an inventory-owned template
listing open `StockoutAlert`s sorted by `days_of_cover`: product, SKU, available, days of cover,
daily velocity, suggested reorder qty. Mounted at `/dashboard/apps/inventory/stockout-forecast/`.
Disabling inventory removes the page (disable-test clean).

### 4.5 Agent tool — `inventory.stockout_forecast` (`agent_tools.py` + `plugin.py`)
Verified `@tool` pattern; complements the static `low_stock_report`.

```
@tool(name='inventory.stockout_forecast', scopes=['inventory.read'],
      description='List SKUs predicted to stock out within N days, with days of cover and a suggested reorder quantity (velocity-based, unlike low_stock_report which is a static threshold).',
      schema={'type':'object','properties':{
          'threshold_days':{'type':'integer','minimum':1,'maximum':90,'default':14},
          'limit':{'type':'integer','minimum':1,'maximum':100,'default':25}}})
def stockout_forecast_tool(*, threshold_days: int = 14, limit: int = 25) -> ToolResult:
    rows = [r for r in forecast_all(threshold_days=threshold_days) if r.reorder_recommended][:limit]
    out = [{'product': r.variant_label, 'available': r.available,
            'days_of_cover': r.days_until_stockout, 'daily_velocity': r.daily_velocity,
            'suggested_reorder_qty': r.suggested_reorder_qty} for r in rows]
    return ToolResult(output={'threshold_days': threshold_days, 'at_risk': out},
                      display=f'{len(out)} SKU(s) projected to stock out within {threshold_days}d')
```

Registered in `contribute_agent_tools()` alongside the existing tools.

### 4.6 Tests (`tests/test_stockout_alerts.py`)
Currently the engine has none. Cover:
- **Engine**: velocity from `movement_type='sale'` movements; days-of-cover math; `reorder_recommended` boundary at `threshold_days`; zero-velocity → `days_until_stockout is None`, not recommended.
- **Reconciler**: opens one alert for a newly at-risk variant; **re-run is idempotent** (no second alert — dedup); resolves on restock; partial-unique-constraint holds.
- **Beat task**: `notify_all_staff` called once for `opened`, **not** for `refreshed`; fail-soft when notifications absent.
- **Agent tool**: output shape; registered & visible to the Worker (scope `inventory.read`).
- **Disable-test**: the DashboardPage + the agent tool vanish when `inventory` is disabled.

## 5. Data flow

```
StockMovement(sale) ──► forecast_all() ──► sync_stockout_alerts() ──► StockoutAlert(open/resolved)
                                                   │                          │
                                          (daily beat task)                   ├─► DashboardPage view
                                                   │                          ├─► agent tool reads forecast_all()
                                                   └─► notify_all_staff (opened only)
```

## 6. Failure handling
- All cross-plugin calls (`notify_all_staff`, self-improvement) are fail-soft try/except — a
  notifications outage never breaks the beat task.
- Beat task has `time_limit`/`soft_time_limit` like the other inventory tasks.
- `forecast_all` already returns `None` days-of-cover for zero-velocity variants; the reconciler
  only ever opens alerts for `reorder_recommended` rows (velocity > 0 within threshold).

## 7. Rollout
- Ships behind the `inventory` plugin (already a default plugin). No feature flag needed; the
  only externally-visible new surface is one dashboard page + bell notifications.
- Migration ships in the same commit as the model (CI `makemigrations --check` gate).
- The beat cadence (daily 06:00 UTC) is overridable via `CELERY_BEAT_SCHEDULE` in settings.

## 8. Torsor / plugin-contract compliance checklist
- [x] Implemented entirely within `plugins/installed/inventory/` (no core edits, no sibling-plugin edits).
- [x] `StockoutAlert` ships with a migration.
- [x] Cross-plugin coupling via service call (`notify_all_staff`) + hooks only — no sibling model imports.
- [x] Disable-test: dashboard page + agent tool are contributions, vanish when inventory is disabled.
- [x] Docs ship with code (this spec; plugin `README`/manifest note on merge).
- [x] No new AI/ML surface needing `core/safety.py` review (deterministic engine).

## 9. Open questions for review
1. **Beat cadence**: daily at 06:00 UTC reasonable, or do you want twice-daily / hourly?
2. **Alert audience**: `notify_all_staff` (every staff user) vs. a future role filter — staff-wide OK for v1?
3. **Page section**: sidebar `section='catalog'` vs `'analytics'` for the Stockout Forecast page?
