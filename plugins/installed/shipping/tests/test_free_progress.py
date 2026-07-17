"""The free-shipping progress tag behind the cart bar."""

from __future__ import annotations

from decimal import Decimal

from django.test import TestCase
from djmoney.money import Money

from plugins.installed.shipping.models import ShippingRate, ShippingZone
from plugins.installed.shipping.templatetags.shipping import free_shipping_progress


class FreeShippingProgressTests(TestCase):
    def _rate(self, threshold, *, active=True):
        z = ShippingZone.objects.create(name='US', countries=['US'])
        return ShippingRate.objects.create(
            zone=z,
            name='Free over',
            computation='free_over',
            free_threshold=Money(Decimal(threshold), 'USD'),
            is_active=active,
        )

    def test_none_subtotal_returns_none(self):
        self._rate('50')
        self.assertIsNone(free_shipping_progress(None))

    def test_no_free_rate_returns_none(self):
        # a flat rate exists but no free_over → bar self-hides
        z = ShippingZone.objects.create(name='US', countries=['US'])
        ShippingRate.objects.create(
            zone=z, name='Flat', computation='flat', flat_amount=Money(5, 'USD')
        )
        self.assertIsNone(free_shipping_progress(Money(30, 'USD')))

    def test_below_threshold_reports_remaining_and_pct(self):
        self._rate('50')
        fs = free_shipping_progress(Money(30, 'USD'))
        self.assertFalse(fs['qualified'])
        self.assertEqual(fs['remaining'], Money(20, 'USD'))
        self.assertEqual(fs['pct'], 60)

    def test_at_or_above_threshold_qualifies(self):
        self._rate('50')
        fs = free_shipping_progress(Money(50, 'USD'))
        self.assertTrue(fs['qualified'])
        self.assertEqual(fs['remaining'], Money(0, 'USD'))
        self.assertEqual(fs['pct'], 100)

    def test_picks_lowest_threshold(self):
        self._rate('80')
        self._rate('40')
        fs = free_shipping_progress(Money(20, 'USD'))
        self.assertEqual(fs['threshold'], Money(40, 'USD'))
        self.assertEqual(fs['pct'], 50)

    def test_inactive_free_rate_ignored(self):
        self._rate('50', active=False)
        self.assertIsNone(free_shipping_progress(Money(30, 'USD')))
