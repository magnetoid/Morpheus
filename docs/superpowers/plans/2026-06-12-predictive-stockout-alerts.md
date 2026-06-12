# Predictive Stockout Alerts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the inventory plugin's existing-but-orphaned demand-forecast engine into a stateful Predictive Stockout Alerts feature (daily job → dedup'd staff alerts → dashboard page → Linda tool), with the tests the engine never had.

**Architecture:** An enhancement to `plugins/installed/inventory/`. A new `StockoutAlert` model (one open row per variant, via a partial unique constraint) gives episode-level dedup. `sync_stockout_alerts()` reconciles `forecast_all()` output against open alerts (open/refresh/resolve). A daily Celery beat task runs it and calls `notify_all_staff` for newly-opened alerts only. A dedicated inventory-owned dashboard page and a `@tool` expose the at-risk list.

**Tech Stack:** Django, Celery (`@app.task` + `register_celery_beat`), the existing `core.agents` `@tool`/`ToolResult`, `notifications_center.services.notify_all_staff`, Django templates.

---

## File Structure

- **Modify** `plugins/installed/inventory/models.py` — add `StockoutAlert`.
- **Create** `plugins/installed/inventory/migrations/0003_stockoutalert.py` — generated; deps `0002_backinstocksubscription`.
- **Modify** `plugins/installed/inventory/demand_forecast.py` — add `sync_stockout_alerts()`.
- **Modify** `plugins/installed/inventory/tasks.py` — add `run_stockout_forecast` task.
- **Modify** `plugins/installed/inventory/agent_tools.py` — add `stockout_forecast_tool`.
- **Modify** `plugins/installed/inventory/views.py` — add `stockout_forecast_view`.
- **Create** `plugins/installed/inventory/templates/inventory/dashboard/stockout_forecast.html`.
- **Modify** `plugins/installed/inventory/plugin.py` — register beat, agent tool, dashboard page.
- **Create** `plugins/installed/inventory/tests/test_stockout_alerts.py`.

**Test command (canonical):**
```bash
DATABASE_URL='sqlite:///:memory:' python manage.py test plugins.installed.inventory.tests.test_stockout_alerts -v2
```
(If the temp fs fills mid-run, prefix `TMPDIR=/Users/magnetoid/.cache/cctmp`.)

**Reference — `forecast_all()` returns `list[ForecastRow]`** with fields: `variant_id: str`, `variant_label: str`, `available: int`, `daily_velocity: float`, `days_until_stockout: float | None`, `reorder_recommended: bool`, `suggested_reorder_qty: int`, `sold_in_window: int`, `window_days: int`. Constants: `DEFAULT_WINDOW_DAYS=28`, `DEFAULT_REORDER_THRESHOLD_DAYS=14`. Velocity counts `StockMovement.movement_type='sale'` (quantity_change negative).

---

## Task 1: `StockoutAlert` model + migration

**Files:**
- Modify: `plugins/installed/inventory/models.py` (append at end)
- Create: `plugins/installed/inventory/migrations/0003_stockoutalert.py`
- Test: `plugins/installed/inventory/tests/test_stockout_alerts.py`

- [ ] **Step 1: Write the failing test**

Create `plugins/installed/inventory/tests/test_stockout_alerts.py`:
```python
"""Predictive Stockout Alerts — model, reconciler, task, tool, dashboard."""
from __future__ import annotations

import uuid
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from plugins.installed.catalog.models import Product, ProductVariant
from plugins.installed.inventory.models import StockLevel, StockMovement, StockoutAlert, Warehouse


def _variant(sku: str) -> ProductVariant:
    p = Product.objects.create(name=f'P-{sku}', slug=f'p-{sku}', status='active')
    return ProductVariant.objects.create(product=p, sku=sku)


class StockoutAlertModelTests(TestCase):
    def test_open_alert_defaults_and_str(self):
        v = _variant('A1')
        a = StockoutAlert.objects.create(variant=v, days_of_cover=3.0,
                                         daily_velocity=2.0, suggested_reorder_qty=40)
        self.assertEqual(a.status, 'open')
        self.assertIsNone(a.resolved_at)
        self.assertIn('A1', str(a))

    def test_one_open_alert_per_variant_enforced(self):
        v = _variant('A2')
        StockoutAlert.objects.create(variant=v)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                StockoutAlert.objects.create(variant=v)  # second OPEN -> constraint

    def test_resolved_does_not_block_a_new_open(self):
        v = _variant('A3')
        first = StockoutAlert.objects.create(variant=v)
        first.status = 'resolved'
        first.resolved_at = timezone.now()
        first.save(update_fields=['status', 'resolved_at'])
        # a fresh open alert for the same variant is now allowed
        StockoutAlert.objects.create(variant=v)
        self.assertEqual(StockoutAlert.objects.filter(variant=v, status='open').count(), 1)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `DATABASE_URL='sqlite:///:memory:' python manage.py test plugins.installed.inventory.tests.test_stockout_alerts.StockoutAlertModelTests -v2`
Expected: FAIL — `ImportError: cannot import name 'StockoutAlert'`.

- [ ] **Step 3: Add the model**

Append to `plugins/installed/inventory/models.py` (uses `uuid`, `models`, `timezone` already imported there — verify the imports at top; add `from django.db.models import Q, UniqueConstraint, Index` usage inline as below):
```python
class StockoutAlert(models.Model):
    """An open episode where a variant is projected to stock out within the
    reorder window. Created by sync_stockout_alerts(); one OPEN row per
    variant (partial unique constraint) so merchants are alerted once per
    episode, not nagged on every forecast run."""

    STATUS_CHOICES = [('open', 'Open'), ('resolved', 'Resolved')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    variant = models.ForeignKey(
        'catalog.ProductVariant', on_delete=models.CASCADE, related_name='stockout_alerts'
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='open', db_index=True)
    days_of_cover = models.FloatField(null=True, blank=True)
    daily_velocity = models.FloatField(default=0)
    suggested_reorder_qty = models.IntegerField(default=0)
    opened_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['days_of_cover']
        constraints = [
            models.UniqueConstraint(
                fields=['variant'],
                condition=models.Q(status='open'),
                name='uniq_open_stockout_alert_per_variant',
            )
        ]
        indexes = [models.Index(fields=['status', 'days_of_cover'])]

    def __str__(self):
        return f'StockoutAlert({self.variant} — {self.status})'
```

- [ ] **Step 4: Generate the migration**

Run: `DATABASE_URL='sqlite:///:memory:' python manage.py makemigrations inventory`
Expected: creates `0003_stockoutalert.py`. Open it and confirm it contains `AddConstraint`/`UniqueConstraint` with `condition=models.Q(status='open')` and `dependencies = [('inventory', '0002_backinstocksubscription')]`.

- [ ] **Step 5: Run the test to verify it passes**

Run: `DATABASE_URL='sqlite:///:memory:' python manage.py test plugins.installed.inventory.tests.test_stockout_alerts.StockoutAlertModelTests -v2`
Expected: PASS (3 tests). If `test_one_open_alert_per_variant_enforced` fails on sqlite, confirm the migration emitted the partial constraint (sqlite supports partial unique indexes).

- [ ] **Step 6: Commit**

```bash
git add plugins/installed/inventory/models.py plugins/installed/inventory/migrations/0003_stockoutalert.py plugins/installed/inventory/tests/test_stockout_alerts.py
git commit -m "feat(inventory): StockoutAlert model for predictive stockout dedup"
```

---

## Task 2: `sync_stockout_alerts()` reconciler

**Files:**
- Modify: `plugins/installed/inventory/demand_forecast.py` (append function)
- Test: `plugins/installed/inventory/tests/test_stockout_alerts.py`

- [ ] **Step 1: Write the failing test**

Append to `test_stockout_alerts.py`:
```python
def _make_at_risk(sku: str, *, on_hand: int, sold: int, window_days: int = 28):
    """A variant with `on_hand` stock and `sold` units of 'sale' movements in
    the window — high velocity so it's projected to stock out."""
    v = _variant(sku)
    wh = Warehouse.objects.create(name=f'WH-{sku}', code=f'WH{sku}')
    sl = StockLevel.objects.create(variant=v, warehouse=wh, quantity=on_hand, reorder_point=0)
    # record `sold` units of sales spread inside the window
    StockMovement.objects.create(stock_level=sl, movement_type='sale',
                                 quantity_change=-sold, quantity_before=on_hand + sold,
                                 quantity_after=on_hand)
    return v, sl


class SyncStockoutAlertsTests(TestCase):
    def test_opens_one_alert_for_a_newly_at_risk_variant(self):
        from plugins.installed.inventory.demand_forecast import sync_stockout_alerts
        _make_at_risk('R1', on_hand=5, sold=140)  # ~5 units/day -> ~1 day of cover
        result = sync_stockout_alerts()
        self.assertEqual(len(result['opened']), 1)
        self.assertEqual(StockoutAlert.objects.filter(status='open').count(), 1)

    def test_rerun_is_idempotent_no_duplicate_alert(self):
        from plugins.installed.inventory.demand_forecast import sync_stockout_alerts
        _make_at_risk('R2', on_hand=5, sold=140)
        sync_stockout_alerts()
        second = sync_stockout_alerts()
        self.assertEqual(len(second['opened']), 0)        # no new alert
        self.assertEqual(second['refreshed'], 1)          # existing one refreshed
        self.assertEqual(StockoutAlert.objects.filter(status='open').count(), 1)

    def test_resolves_when_restocked(self):
        from plugins.installed.inventory.demand_forecast import sync_stockout_alerts
        v, sl = _make_at_risk('R3', on_hand=5, sold=140)
        sync_stockout_alerts()
        sl.quantity = 5000          # big restock -> many days of cover -> not at risk
        sl.save(update_fields=['quantity'])
        result = sync_stockout_alerts()
        self.assertEqual(result['resolved'], 1)
        self.assertEqual(StockoutAlert.objects.filter(status='open').count(), 0)
```

- [ ] **Step 2: Run to verify it fails**

Run: `DATABASE_URL='sqlite:///:memory:' python manage.py test plugins.installed.inventory.tests.test_stockout_alerts.SyncStockoutAlertsTests -v2`
Expected: FAIL — `ImportError: cannot import name 'sync_stockout_alerts'`.

- [ ] **Step 3: Implement the reconciler**

Append to `plugins/installed/inventory/demand_forecast.py`:
```python
def sync_stockout_alerts(
    *,
    window_days: int = DEFAULT_WINDOW_DAYS,
    threshold_days: int = DEFAULT_REORDER_THRESHOLD_DAYS,
) -> dict:
    """Reconcile the forecast against open StockoutAlerts.

    Opens an alert for each newly at-risk variant, refreshes the snapshot of
    ones still at risk, and resolves ones that have recovered. Returns
    {'opened': [StockoutAlert, ...], 'refreshed': int, 'resolved': int}.
    """
    from django.utils import timezone  # noqa: PLC0415

    from plugins.installed.inventory.models import StockoutAlert  # noqa: PLC0415

    rows = forecast_all(window_days=window_days, threshold_days=threshold_days)
    at_risk = {r.variant_id: r for r in rows if r.reorder_recommended}
    open_alerts = {
        str(a.variant_id): a for a in StockoutAlert.objects.filter(status='open')
    }

    opened: list = []
    refreshed = 0
    for vid, row in at_risk.items():
        existing = open_alerts.get(str(vid))
        if existing is not None:
            existing.days_of_cover = row.days_until_stockout
            existing.daily_velocity = row.daily_velocity
            existing.suggested_reorder_qty = row.suggested_reorder_qty
            existing.save(update_fields=[
                'days_of_cover', 'daily_velocity', 'suggested_reorder_qty', 'last_seen_at'
            ])
            refreshed += 1
        else:
            opened.append(StockoutAlert.objects.create(
                variant_id=vid,
                days_of_cover=row.days_until_stockout,
                daily_velocity=row.daily_velocity,
                suggested_reorder_qty=row.suggested_reorder_qty,
            ))

    resolved = 0
    for vid, alert in open_alerts.items():
        if vid not in {str(k) for k in at_risk}:
            alert.status = 'resolved'
            alert.resolved_at = timezone.now()
            alert.save(update_fields=['status', 'resolved_at'])
            resolved += 1

    return {'opened': opened, 'refreshed': refreshed, 'resolved': resolved}
```

- [ ] **Step 4: Run to verify it passes**

Run: `DATABASE_URL='sqlite:///:memory:' python manage.py test plugins.installed.inventory.tests.test_stockout_alerts.SyncStockoutAlertsTests -v2`
Expected: PASS (3 tests). If `test_opens...` finds 0 at-risk, raise `sold` so daily velocity clearly exceeds `available / threshold_days`.

- [ ] **Step 5: Commit**

```bash
git add plugins/installed/inventory/demand_forecast.py plugins/installed/inventory/tests/test_stockout_alerts.py
git commit -m "feat(inventory): sync_stockout_alerts reconciler (open/refresh/resolve)"
```

---

## Task 3: Daily beat task + staff notification

**Files:**
- Modify: `plugins/installed/inventory/tasks.py` (append task)
- Modify: `plugins/installed/inventory/plugin.py` (register beat in `ready()`)
- Test: `plugins/installed/inventory/tests/test_stockout_alerts.py`

- [ ] **Step 1: Write the failing test**

Append to `test_stockout_alerts.py`:
```python
from unittest import mock


class RunStockoutForecastTaskTests(TestCase):
    def test_notifies_staff_only_for_newly_opened(self):
        from plugins.installed.inventory import tasks
        _make_at_risk('T1', on_hand=5, sold=140)
        with mock.patch.object(tasks, 'notify_all_staff', return_value=1) as m:
            first = tasks.run_stockout_forecast()
            self.assertEqual(first['opened'], 1)
            m.assert_called_once()
            self.assertEqual(m.call_args.kwargs['kind'], 'inventory.stockout_forecast')
        # second run: still at risk, refreshed not opened -> NO notification
        with mock.patch.object(tasks, 'notify_all_staff', return_value=1) as m2:
            second = tasks.run_stockout_forecast()
            self.assertEqual(second['opened'], 0)
            m2.assert_not_called()
```

- [ ] **Step 2: Run to verify it fails**

Run: `DATABASE_URL='sqlite:///:memory:' python manage.py test plugins.installed.inventory.tests.test_stockout_alerts.RunStockoutForecastTaskTests -v2`
Expected: FAIL — `AttributeError: module ... has no attribute 'run_stockout_forecast'`.

- [ ] **Step 3: Implement the task**

In `plugins/installed/inventory/tasks.py`, add a module-level import near the top (after `from morph.celery import app`):
```python
try:
    from plugins.installed.notifications_center.services import notify_all_staff
except ImportError:  # notifications_center not installed
    def notify_all_staff(**kwargs) -> int:  # fail-soft stub
        return 0
```
Then append the task:
```python
@app.task(
    name='inventory.run_stockout_forecast', ignore_result=True, time_limit=120, soft_time_limit=90
)
def run_stockout_forecast() -> dict:
    """Daily: reconcile stockout alerts; alert staff for newly opened ones."""
    from plugins.installed.inventory.demand_forecast import sync_stockout_alerts  # noqa: PLC0415

    result = sync_stockout_alerts()
    newly = result['opened']
    if newly:
        lines = '\n'.join(
            f'{a.variant} — ~{(a.days_of_cover or 0):.0f}d of cover, reorder {a.suggested_reorder_qty}'
            for a in newly[:10]
        )
        try:
            notify_all_staff(
                kind='inventory.stockout_forecast',
                title=f'{len(newly)} SKU(s) projected to stock out soon',
                body=lines,
                action_url='/dashboard/apps/inventory/stockout-forecast/',
                icon='alert-triangle',
            )
        except Exception as exc:  # noqa: BLE001 — alerting never breaks the job
            logger.warning('run_stockout_forecast: notify failed: %s', exc, exc_info=True)
    return {'opened': len(newly), 'resolved': result['resolved']}
```

- [ ] **Step 4: Register the daily beat schedule**

In `plugins/installed/inventory/plugin.py`, add the import at the top of the file (next to `from morpheus import Plugin, events`):
```python
from celery.schedules import crontab
```
Then inside `ready()`, after the existing `register_celery_beat('inventory:reconcile_redis_stock', ...)` block, add:
```python
        # Daily predictive stockout forecast → dedup'd staff alerts.
        self.register_celery_beat(
            'inventory:run_stockout_forecast',
            {
                'task': 'inventory.run_stockout_forecast',
                'schedule': crontab(hour=6, minute=0),  # 06:00 UTC daily
            },
        )
```

- [ ] **Step 5: Run to verify it passes**

Run: `DATABASE_URL='sqlite:///:memory:' python manage.py test plugins.installed.inventory.tests.test_stockout_alerts.RunStockoutForecastTaskTests -v2`
Expected: PASS (1 test).

- [ ] **Step 6: Commit**

```bash
git add plugins/installed/inventory/tasks.py plugins/installed/inventory/plugin.py plugins/installed/inventory/tests/test_stockout_alerts.py
git commit -m "feat(inventory): daily run_stockout_forecast beat task + staff alerts"
```

---

## Task 4: `inventory.stockout_forecast` agent tool

**Files:**
- Modify: `plugins/installed/inventory/agent_tools.py` (append tool)
- Modify: `plugins/installed/inventory/plugin.py` (`contribute_agent_tools`)
- Test: `plugins/installed/inventory/tests/test_stockout_alerts.py`

- [ ] **Step 1: Write the failing test**

Append to `test_stockout_alerts.py`:
```python
class StockoutForecastToolTests(TestCase):
    def test_tool_returns_at_risk_rows(self):
        from plugins.installed.inventory.agent_tools import stockout_forecast_tool
        _make_at_risk('G1', on_hand=5, sold=140)
        result = stockout_forecast_tool.invoke({'threshold_days': 14, 'limit': 25})
        self.assertGreaterEqual(len(result.output['at_risk']), 1)
        self.assertIn('suggested_reorder_qty', result.output['at_risk'][0])

    def test_tool_registered_and_worker_visible(self):
        from core.agents import agent_registry
        names = {t.name for t in agent_registry.platform_tools()}
        self.assertIn('inventory.stockout_forecast', names)
        worker = agent_registry.get_agent('worker')
        self.assertIn('inventory.stockout_forecast', {t.name for t in worker.get_tools()})
```

- [ ] **Step 2: Run to verify it fails**

Run: `DATABASE_URL='sqlite:///:memory:' python manage.py test plugins.installed.inventory.tests.test_stockout_alerts.StockoutForecastToolTests -v2`
Expected: FAIL — `ImportError: cannot import name 'stockout_forecast_tool'`.

- [ ] **Step 3: Implement the tool**

Append to `plugins/installed/inventory/agent_tools.py` (imports `tool`, `ToolResult` already present at top — verify):
```python
@tool(
    name='inventory.stockout_forecast',
    description=(
        'List SKUs predicted to stock out within N days, with days of cover, '
        'daily velocity and a suggested reorder quantity. Velocity-based — unlike '
        'inventory.low_stock_report which is a static threshold.'
    ),
    scopes=['inventory.read'],
    schema={
        'type': 'object',
        'properties': {
            'threshold_days': {'type': 'integer', 'minimum': 1, 'maximum': 90, 'default': 14},
            'limit': {'type': 'integer', 'minimum': 1, 'maximum': 100, 'default': 25},
        },
    },
)
def stockout_forecast_tool(*, threshold_days: int = 14, limit: int = 25) -> ToolResult:
    from plugins.installed.inventory.demand_forecast import forecast_all  # noqa: PLC0415

    threshold_days = max(1, min(int(threshold_days or 14), 90))
    limit = max(1, min(int(limit or 25), 100))
    rows = [r for r in forecast_all(threshold_days=threshold_days) if r.reorder_recommended][:limit]
    out = [
        {
            'product': r.variant_label,
            'available': r.available,
            'days_of_cover': r.days_until_stockout,
            'daily_velocity': round(r.daily_velocity, 2),
            'suggested_reorder_qty': r.suggested_reorder_qty,
        }
        for r in rows
    ]
    return ToolResult(
        output={'threshold_days': threshold_days, 'at_risk': out},
        display=f'{len(out)} SKU(s) projected to stock out within {threshold_days}d',
    )
```

- [ ] **Step 4: Register the tool**

In `plugins/installed/inventory/plugin.py` `contribute_agent_tools()`, add `stockout_forecast_tool` to both the import block and the returned list:
```python
    def contribute_agent_tools(self) -> list:
        from plugins.installed.inventory.agent_tools import (  # noqa: PLC0415
            adjust_stock_tool,
            list_back_in_stock_tool,
            low_stock_report_tool,
            schedule_price_change_tool,
            stockout_forecast_tool,
        )

        return [
            low_stock_report_tool,
            adjust_stock_tool,
            list_back_in_stock_tool,
            schedule_price_change_tool,
            stockout_forecast_tool,
        ]
```

- [ ] **Step 5: Run to verify it passes**

Run: `DATABASE_URL='sqlite:///:memory:' python manage.py test plugins.installed.inventory.tests.test_stockout_alerts.StockoutForecastToolTests -v2`
Expected: PASS (2 tests). `worker.get_tools()` includes it because the Worker scope set already contains `inventory.read`/`inventory.write`.

- [ ] **Step 6: Commit**

```bash
git add plugins/installed/inventory/agent_tools.py plugins/installed/inventory/plugin.py plugins/installed/inventory/tests/test_stockout_alerts.py
git commit -m "feat(inventory): inventory.stockout_forecast agent tool"
```

---

## Task 5: Stockout Forecast dashboard page

**Files:**
- Modify: `plugins/installed/inventory/views.py` (append view)
- Create: `plugins/installed/inventory/templates/inventory/dashboard/stockout_forecast.html`
- Modify: `plugins/installed/inventory/plugin.py` (`contribute_dashboard_pages`)
- Test: `plugins/installed/inventory/tests/test_stockout_alerts.py`

- [ ] **Step 1: Write the failing test**

Append to `test_stockout_alerts.py`:
```python
class StockoutForecastPageTests(TestCase):
    def setUp(self):
        self.staff = __import__('django.contrib.auth', fromlist=['get_user_model']).get_user_model().objects.create_user(
            username='ops', email='ops@example.com', password='x', is_staff=True
        )

    def test_page_lists_open_alerts(self):
        v = _variant('D1')
        StockoutAlert.objects.create(variant=v, days_of_cover=2.0, suggested_reorder_qty=30)
        self.client.force_login(self.staff)
        resp = self.client.get('/dashboard/apps/inventory/stockout-forecast/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'D1')

    def test_page_requires_staff(self):
        resp = self.client.get('/dashboard/apps/inventory/stockout-forecast/')
        self.assertIn(resp.status_code, (301, 302, 403))

    def test_dashboard_page_contributed_and_disable_clean(self):
        from plugins.registry import plugin_registry
        slugs = {p.slug for p in plugin_registry.dashboard_pages() if p.plugin == 'inventory'}
        self.assertIn('stockout-forecast', slugs)
```

- [ ] **Step 2: Run to verify it fails**

Run: `DATABASE_URL='sqlite:///:memory:' python manage.py test plugins.installed.inventory.tests.test_stockout_alerts.StockoutForecastPageTests -v2`
Expected: FAIL — 404 on the URL / `stockout-forecast` not in contributed pages.

- [ ] **Step 3: Add the view**

Append to `plugins/installed/inventory/views.py`:
```python
def stockout_forecast_view(request: HttpRequest) -> HttpResponse:
    """Dashboard page: open predictive stockout alerts, worst cover first."""
    from morpheus.views import render, staff_member_required  # noqa: PLC0415

    @staff_member_required
    def _inner(req: HttpRequest) -> HttpResponse:
        from plugins.installed.inventory.models import StockoutAlert  # noqa: PLC0415

        alerts = list(
            StockoutAlert.objects.filter(status='open')
            .select_related('variant', 'variant__product')
            .order_by('days_of_cover')[:200]
        )
        return render(
            req, 'inventory/dashboard/stockout_forecast.html',
            {'alerts': alerts, 'active_nav': 'apps'},
        )

    return _inner(request)
```
(If `morpheus.views` does not re-export `staff_member_required`/`render`, import from `django.contrib.admin.views.decorators` and `django.shortcuts` respectively — verify against `plugins/installed/admin_dashboard/views_split/apps.py` which uses `from morpheus.views import ... staff_member_required, render`.)

- [ ] **Step 4: Add the template**

Create `plugins/installed/inventory/templates/inventory/dashboard/stockout_forecast.html`:
```django
{% extends "admin_dashboard/base.html" %}
{% block title %}Stockout Forecast{% endblock %}
{% block content %}
<div class="page-head">
  <h1>Stockout Forecast</h1>
  <p class="muted">SKUs projected to run out within the reorder window, worst cover first.</p>
</div>
{% if alerts %}
<table class="morph-table">
  <thead><tr><th>Product</th><th>SKU</th><th>Days of cover</th><th>Velocity / day</th><th>Suggested reorder</th></tr></thead>
  <tbody>
  {% for a in alerts %}
    <tr>
      <td>{{ a.variant.product.name }}</td>
      <td>{{ a.variant.sku }}</td>
      <td>{% if a.days_of_cover is not None %}{{ a.days_of_cover|floatformat:1 }}{% else %}—{% endif %}</td>
      <td>{{ a.daily_velocity|floatformat:2 }}</td>
      <td>{{ a.suggested_reorder_qty }}</td>
    </tr>
  {% endfor %}
  </tbody>
</table>
{% else %}
<p class="muted">No SKUs are projected to stock out. 🎉</p>
{% endif %}
{% endblock %}
```
(Verify the base template's block names against `plugins/installed/admin_dashboard/templates/admin_dashboard/base.html` — adjust `{% block content %}`/`{% block title %}` if it uses different names.)

- [ ] **Step 5: Contribute the dashboard page**

In `plugins/installed/inventory/plugin.py`, add a method (next to `contribute_agent_tools`):
```python
    def contribute_dashboard_pages(self) -> list:
        from morpheus import DashboardPage  # noqa: PLC0415

        return [
            DashboardPage(
                label='Stockout Forecast',
                slug='stockout-forecast',
                view='plugins.installed.inventory.views.stockout_forecast_view',
                icon='trending-down',
                section='catalog',
                nav='main',
            )
        ]
```

- [ ] **Step 6: Run to verify it passes**

Run: `DATABASE_URL='sqlite:///:memory:' python manage.py test plugins.installed.inventory.tests.test_stockout_alerts.StockoutForecastPageTests -v2`
Expected: PASS (3 tests). If the page 404s, confirm the registry mounts `contribute_dashboard_pages` views at `/dashboard/apps/<plugin>/<slug>/` (it does — see `plugins/contributions.py:DashboardPage` docstring).

- [ ] **Step 7: Commit**

```bash
git add plugins/installed/inventory/views.py plugins/installed/inventory/templates/inventory/dashboard/stockout_forecast.html plugins/installed/inventory/plugin.py plugins/installed/inventory/tests/test_stockout_alerts.py
git commit -m "feat(inventory): Stockout Forecast dashboard page"
```

---

## Task 6: Full-plugin verification + system checks

**Files:** none (verification only)

- [ ] **Step 1: Run the whole new test module**

Run: `DATABASE_URL='sqlite:///:memory:' python manage.py test plugins.installed.inventory.tests.test_stockout_alerts -v2`
Expected: PASS (all classes: model 3, sync 3, task 1, tool 2, page 3).

- [ ] **Step 2: Run the entire inventory test suite (no regressions)**

Run: `DATABASE_URL='sqlite:///:memory:' python manage.py test plugins.installed.inventory -v1`
Expected: OK, 0 failures/errors.

- [ ] **Step 3: System + migration checks**

Run:
```bash
DATABASE_URL='sqlite:///:memory:' python manage.py check
DATABASE_URL='sqlite:///:memory:' python manage.py makemigrations --check --dry-run
```
Expected: "System check identified no issues"; "No changes detected" (migration already committed).

- [ ] **Step 4: Lint the touched files (CI parity)**

Run: `ruff check plugins/installed/inventory/ && ruff format --check plugins/installed/inventory/`
Expected: passes (or only the project's known pre-existing PLC0415 lazy-import noise on files you didn't add lines to).

- [ ] **Step 5: Final commit (docs/manifest note)**

Add a one-line feature note to the inventory plugin docstring/README if present, then:
```bash
git add -A
git commit -m "docs(inventory): note Predictive Stockout Alerts in plugin"
```

---

## Self-Review

**Spec coverage:** model §4.1→T1; reconciler §4.2→T2; beat+alert §4.3→T3; agent tool §4.5→T4; dashboard page §4.4→T5; tests §4.6→T1-T5 + T6 regression. All covered.

**Open-question defaults baked in:** daily 06:00 UTC (T3 crontab), `notify_all_staff` staff-wide (T3), `section='catalog'` (T5).

**Type consistency:** `sync_stockout_alerts()` returns `{'opened': list, 'refreshed': int, 'resolved': int}` — used consistently in T2 tests and T3 task. `ForecastRow` field names (`variant_id`, `variant_label`, `available`, `daily_velocity`, `days_until_stockout`, `reorder_recommended`, `suggested_reorder_qty`) match the verified dataclass. `StockoutAlert` fields match T1 model and T2/T5 usage.

**No placeholders:** every code step has complete code; two "verify against base template / morpheus.views re-export" notes are confirmation checks with explicit fallbacks, not missing content.
