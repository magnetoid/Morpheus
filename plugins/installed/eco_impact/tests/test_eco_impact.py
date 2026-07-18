"""eco_impact — footprint math, checkout offset, and pledge ledger."""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from djmoney.money import Money

from plugins.installed.eco_impact import footprint, services
from plugins.installed.eco_impact.models import TreePledge
from plugins.installed.eco_impact.plugin import EcoImpactPlugin
from plugins.installed.orders.models import Order

User = get_user_model()


class FootprintMathTests(SimpleTestCase):
    def test_weight_based(self):
        r = footprint.impact(weight_g=300, print_type='paperback')
        self.assertTrue(r['has_data'])
        self.assertAlmostEqual(r['paper_g'], 255.0, places=1)
        self.assertGreater(r['wood_g'], r['paper_g'])  # wood factor > 1
        self.assertGreater(r['co2_kg'], 0)

    def test_estimate_from_pages_when_no_weight(self):
        r = footprint.impact(page_count=320, width_mm=129, height_mm=198, print_type='paperback')
        self.assertTrue(r['has_data'])
        self.assertGreater(r['paper_g'], 0)

    def test_no_data_returns_flag_false(self):
        r = footprint.impact(print_type='paperback')
        self.assertFalse(r['has_data'])
        self.assertEqual(r['co2_kg'], 0.0)

    def test_factor_override_applied(self):
        base = footprint.impact(weight_g=300)
        doubled = footprint.impact(weight_g=300, factors={'wood_factor': 5.0})
        self.assertAlmostEqual(doubled['wood_g'], base['wood_g'] * 2, places=1)


class _Cart:
    """Lightweight stand-in — the breakdown subscriber only reads .metadata."""

    def __init__(self, optin: bool):
        self.metadata = {'eco_impact_optin': True} if optin else {}


class BreakdownSurchargeTests(TestCase):
    def setUp(self):
        self.plugin = EcoImpactPlugin()

    def _value(self, total=20):
        return {'currency': 'USD', 'total': Money(total, 'USD'), 'meta': {}}

    def test_surcharge_added_only_when_opted_in(self):
        v = self.plugin.on_cart_breakdown(self._value(20), cart=_Cart(True))
        self.assertEqual(v['total'], Money(Decimal('21.50'), 'USD'))
        self.assertEqual(v['meta']['eco_impact']['trees'], 1)

    def test_no_change_when_not_opted_in(self):
        v = self.plugin.on_cart_breakdown(self._value(20), cart=_Cart(False))
        self.assertEqual(v['total'], Money(20, 'USD'))
        self.assertNotIn('eco_impact', v['meta'])

    def test_fail_soft_on_bad_value(self):
        # A non-dict value returns unchanged and never raises.
        self.assertIsNone(self.plugin.on_cart_breakdown(None, cart=_Cart(True)))


class PledgeLedgerTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='r', email='r@example.com', password='x')

    def _order(self):
        return Order.objects.create(
            customer=self.user,
            email=self.user.email,
            subtotal=Money(30, 'USD'),
            total=Money(30, 'USD'),
        )

    def test_record_pledge_idempotent(self):
        order = self._order()
        first = services.record_pledge(order, trees=1, amount='1.50', currency='USD')
        self.assertIsNotNone(first)
        again = services.record_pledge(order, trees=1, amount='1.50', currency='USD')
        self.assertIsNone(again)  # OneToOne → no duplicate on retry
        self.assertEqual(TreePledge.objects.filter(order=order).count(), 1)

    def test_store_totals(self):
        for _ in range(3):
            services.record_pledge(self._order(), trees=1, amount='1.50')
        totals = services.store_totals()
        self.assertEqual(totals['trees'], 3)
        self.assertEqual(totals['contributors'], 3)
        self.assertGreater(totals['co2_offset_kg'], 0)

    def test_remove_pledge_on_cancel(self):
        order = self._order()
        services.record_pledge(order, trees=1, amount='1.50')
        services.remove_pledge(order)
        self.assertEqual(TreePledge.objects.filter(order=order).count(), 0)
