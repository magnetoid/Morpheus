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
    p = Product.objects.create(name=f'P-{sku}', slug=f'p-{sku}', status='active', price=10)
    return ProductVariant.objects.create(product=p, sku=sku)


class StockoutAlertModelTests(TestCase):
    def test_open_alert_defaults_and_str(self):
        v = _variant('A1')
        a = StockoutAlert.objects.create(
            variant=v, days_of_cover=3.0, daily_velocity=2.0, suggested_reorder_qty=40
        )
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


def _make_at_risk(sku: str, *, on_hand: int, sold: int):
    """A variant with `on_hand` stock and `sold` units of 'sale' movements in
    the window — high velocity so it's projected to stock out."""
    v = _variant(sku)
    wh = Warehouse.objects.create(name=f'WH-{sku}', code=f'WH{sku}')
    sl = StockLevel.objects.create(variant=v, warehouse=wh, quantity=on_hand, reorder_point=0)
    StockMovement.objects.create(
        stock_level=sl,
        movement_type='sale',
        quantity_change=-sold,
        quantity_before=on_hand + sold,
        quantity_after=on_hand,
    )
    return v, sl


class SyncStockoutAlertsTests(TestCase):
    def test_opens_one_alert_for_a_newly_at_risk_variant(self):
        from plugins.installed.inventory.demand_forecast import sync_stockout_alerts

        _make_at_risk('R1', on_hand=5, sold=140)
        result = sync_stockout_alerts()
        self.assertEqual(len(result['opened']), 1)
        self.assertEqual(StockoutAlert.objects.filter(status='open').count(), 1)

    def test_rerun_is_idempotent_no_duplicate_alert(self):
        from plugins.installed.inventory.demand_forecast import sync_stockout_alerts

        _make_at_risk('R2', on_hand=5, sold=140)
        sync_stockout_alerts()
        second = sync_stockout_alerts()
        self.assertEqual(len(second['opened']), 0)
        self.assertEqual(second['refreshed'], 1)
        self.assertEqual(StockoutAlert.objects.filter(status='open').count(), 1)

    def test_resolves_when_restocked(self):
        from plugins.installed.inventory.demand_forecast import sync_stockout_alerts

        v, sl = _make_at_risk('R3', on_hand=5, sold=140)
        sync_stockout_alerts()
        sl.quantity = 5000
        sl.save(update_fields=['quantity'])
        result = sync_stockout_alerts()
        self.assertEqual(result['resolved'], 1)
        self.assertEqual(StockoutAlert.objects.filter(status='open').count(), 0)


class RunStockoutForecastTaskTests(TestCase):
    def test_notifies_staff_only_for_newly_opened(self):
        from unittest import mock

        from plugins.installed.inventory import tasks

        _make_at_risk('T1', on_hand=5, sold=140)
        with mock.patch.object(tasks, 'notify_all_staff', return_value=1) as m:
            first = tasks.run_stockout_forecast()
            self.assertEqual(first['opened'], 1)
            m.assert_called_once()
            self.assertEqual(m.call_args.kwargs['kind'], 'inventory.stockout_forecast')
        with mock.patch.object(tasks, 'notify_all_staff', return_value=1) as m2:
            second = tasks.run_stockout_forecast()
            self.assertEqual(second['opened'], 0)
            m2.assert_not_called()


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
