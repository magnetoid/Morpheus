"""The shipping page lists the configured rates, never theme copy (v0.128.0).

dotbooks' page promised "$5 flat", Express and free shipping over $40 while no
store had a single rate, so checkout charged nothing for shipping.
"""

from __future__ import annotations

from decimal import Decimal

from django.test import TestCase
from djmoney.money import Money

from plugins.installed.shipping.models import ShippingRate, ShippingZone
from plugins.installed.shipping.templatetags.shipping import shipping_rate_cards


class RateCardTests(TestCase):
    def setUp(self):
        self.zone = ShippingZone.objects.create(name='Domestic — US', countries=['US'])

    def _rate(self, name, computation, **fields):
        return ShippingRate.objects.create(
            zone=self.zone, name=name, computation=computation, **fields
        )

    def test_no_rates_no_cards(self):
        self.assertEqual(shipping_rate_cards(), [])

    def test_each_kind_says_what_checkout_charges(self):
        self._rate('Standard', 'flat', flat_amount=Money(5, 'USD'), priority=1)
        self._rate(
            'Free over',
            'free_over',
            flat_amount=Money(5, 'USD'),
            free_threshold=Money(40, 'USD'),
            priority=2,
        )
        self._rate('Tiered', 'order_total_tier', tiers=[{'threshold': 0, 'amount': 7}], priority=3)
        self._rate('Live', 'carrier_shippo', priority=4)
        self._rate('Broken', 'flat', priority=5)  # no amount: checkout cannot quote it
        self._rate('Off', 'flat', flat_amount=Money(1, 'USD'), is_active=False)
        cards = {c['name']: c for c in shipping_rate_cards()}
        self.assertEqual(set(cards), {'Standard', 'Free over', 'Tiered', 'Live'})
        self.assertEqual(cards['Standard']['price'], Money(5, 'USD'))
        self.assertEqual(cards['Free over']['free_over'], Money(40, 'USD'))
        self.assertEqual(
            (cards['Tiered']['kind'], cards['Tiered']['price']), ('from', Money(Decimal(7), 'USD'))
        )
        self.assertEqual(cards['Live']['kind'], 'live')

    def test_the_shipping_page_without_rates_promises_nothing(self):
        body = self.client.get('/shipping/').content.decode()
        self.assertIn('Checkout shows the delivery options for your address', body)
        for claim in ('$5 flat', 'over $40', 'How do I claim free shipping'):
            self.assertNotIn(claim, body)

    def test_the_shipping_page_lists_the_rates(self):
        self._rate(
            'Standard',
            'free_over',
            flat_amount=Money(5, 'USD'),
            free_threshold=Money(40, 'USD'),
            estimated_days_min=3,
            estimated_days_max=5,
        )
        body = self.client.get('/shipping/').content.decode()
        self.assertIn('Standard', body)
        self.assertIn('free on orders over $40.00', body)
        self.assertIn('3–5 business days', body)
