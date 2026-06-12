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
