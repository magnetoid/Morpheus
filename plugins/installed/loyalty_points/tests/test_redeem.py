"""Redemption v1 tests: discount math, ledger service, account surface.

Covers the points→Money helpers, the ``redeem_points`` /
``reverse_redemption`` ledger services, and the customer-facing
``/account/points/`` boundary triplet (anon blocked / authed sees only
their own balance / a second customer can't see the first's points).
"""

# ruff: noqa: PLC0415, I001
# Inline imports are intentional in tests — avoid touching the app
# registry at module-import time.
from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from djmoney.money import Money


def _make_user(email: str, password: str = 'pw'):
    return get_user_model().objects.create_user(
        username=email,
        email=email,
        password=password,
    )


class RedemptionMathTests(TestCase):
    """Pure helpers — no DB needed beyond the default rate."""

    def test_points_to_amount_default_rate(self):
        from plugins.installed.loyalty_points.services_redeem import points_to_amount

        # 100 pts = 1.00 at the default rate.
        self.assertEqual(points_to_amount(100).amount, Decimal('1.00'))
        self.assertEqual(points_to_amount(250).amount, Decimal('2.50'))

    def test_points_to_amount_rounds_down(self):
        from plugins.installed.loyalty_points.services_redeem import points_to_amount

        # 149 pts → 1.49 (round DOWN, never over-credit).
        self.assertEqual(points_to_amount(149).amount, Decimal('1.49'))

    def test_amount_to_points_rounds_up(self):
        from plugins.installed.loyalty_points.services_redeem import amount_to_points

        self.assertEqual(amount_to_points(Money(Decimal('1.00'), 'USD')), 100)
        # 1.001 worth → ceil to 101 pts so the grant never exceeds spend.
        self.assertEqual(amount_to_points(Decimal('1.001')), 101)

    def test_negative_points_floor_at_zero(self):
        from plugins.installed.loyalty_points.services_redeem import points_to_amount

        self.assertEqual(points_to_amount(-50).amount, Decimal('0'))


class RedeemServiceTests(TestCase):
    def setUp(self):
        self.user = _make_user('redeemer@example.com')
        from plugins.installed.loyalty_points import services

        services.award_points(self.user, 500, reason='earn_order', order_number='O-1')

    def test_redeem_records_negative_txn_and_returns_money(self):
        from plugins.installed.loyalty_points import services
        from plugins.installed.loyalty_points.services_redeem import redeem_points

        money = redeem_points(self.user, 300, reason='checkout')
        self.assertEqual(money.amount, Decimal('3.00'))
        # Balance debited.
        self.assertEqual(services.get_balance(self.user), 200)
        # A spend_order row exists with negative points.
        from plugins.installed.loyalty_points.models import PointsTransaction

        spend = PointsTransaction.objects.get(customer=self.user, reason='spend_order')
        self.assertEqual(spend.points, -300)

    def test_redeem_more_than_balance_raises(self):
        from plugins.installed.loyalty_points.services_redeem import redeem_points

        with self.assertRaises(ValueError):
            redeem_points(self.user, 9999)

    def test_redeem_non_positive_raises(self):
        from plugins.installed.loyalty_points.services_redeem import redeem_points

        with self.assertRaises(ValueError):
            redeem_points(self.user, 0)

    def test_reverse_redemption_recredits(self):
        from plugins.installed.loyalty_points import services
        from plugins.installed.loyalty_points.services_redeem import (
            redeem_points,
            reverse_redemption,
        )

        redeem_points(self.user, 300)
        self.assertEqual(services.get_balance(self.user), 200)
        reverse_redemption(self.user, 300, reason='order cancelled')
        self.assertEqual(services.get_balance(self.user), 500)

    def test_max_redeemable_caps_at_order_value(self):
        from plugins.installed.loyalty_points.services_redeem import max_redeemable

        # Balance is 500 pts (= 5.00). A 2.00 order caps at 200 pts.
        capped = max_redeemable(self.user, order_total=Money(Decimal('2.00'), 'USD'))
        self.assertEqual(capped, 200)
        # Without an order total, the cap is just the balance.
        self.assertEqual(max_redeemable(self.user), 500)


class _FakeCart:
    """Minimal cart stand-in for the breakdown hook contract test."""

    def __init__(self, customer, redeem):
        self.customer = customer
        self.metadata = {'loyalty_points_redeem': redeem}


class BreakdownHookTests(TestCase):
    def setUp(self):
        self.user = _make_user('cart@example.com')
        from plugins.installed.loyalty_points import services

        services.award_points(self.user, 500, reason='earn_order', order_number='C-1')
        from plugins.installed.loyalty_points.plugin import LoyaltyPointsPlugin

        self.plugin = LoyaltyPointsPlugin()

    def _breakdown(self, total='10.00'):
        return {
            'currency': 'USD',
            'subtotal': Money(Decimal(total), 'USD'),
            'shipping': Money(Decimal('0'), 'USD'),
            'tax': Money(Decimal('0'), 'USD'),
            'discount': Money(Decimal('0'), 'USD'),
            'total': Money(Decimal(total), 'USD'),
            'meta': {},
        }

    def test_hook_applies_capped_points_discount(self):
        cart = _FakeCart(self.user, redeem=300)
        out = self.plugin.on_cart_breakdown(self._breakdown('10.00'), cart=cart, customer=self.user)
        # 300 pts = 3.00 off a 10.00 order.
        self.assertEqual(out['discount'].amount, Decimal('3.00'))
        self.assertEqual(out['total'].amount, Decimal('7.00'))
        self.assertEqual(out['meta']['loyalty_points']['points'], 300)

    def test_hook_caps_at_order_total(self):
        # Ask for 5.00 worth (500 pts) on a 2.00 order — capped to 2.00.
        cart = _FakeCart(self.user, redeem=500)
        out = self.plugin.on_cart_breakdown(self._breakdown('2.00'), cart=cart, customer=self.user)
        self.assertEqual(out['discount'].amount, Decimal('2.00'))
        self.assertEqual(out['total'].amount, Decimal('0.00'))

    def test_hook_noop_without_redeem_metadata(self):
        cart = _FakeCart(self.user, redeem=0)
        out = self.plugin.on_cart_breakdown(self._breakdown('10.00'), cart=cart, customer=self.user)
        self.assertEqual(out['discount'].amount, Decimal('0'))
        self.assertNotIn('loyalty_points', out.get('meta', {}))


class AccountPointsBoundaryTests(TestCase):
    """Boundary triplet for the customer-scoped /account/points/ view.

    * anon → redirected to login (no balance leak)
    * authed customer → 200, sees ONLY their own balance
    * a second customer → 200, never sees the first customer's points
    """

    def setUp(self):
        self.client = Client()
        self.alice = _make_user('alice@example.com')
        self.bob = _make_user('bob@example.com')
        from plugins.installed.loyalty_points import services

        services.award_points(self.alice, 420, reason='earn_order', order_number='A-1')

    def test_anon_redirected_to_login(self):
        resp = self.client.get('/account/points/')
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/auth/login/', resp['Location'])

    def test_owner_sees_own_balance(self):
        self.client.force_login(self.alice)
        resp = self.client.get('/account/points/')
        self.assertEqual(resp.status_code, 200)
        # Match the rendered balance ("{{ balance }} points") rather than a
        # bare "420" — the theme's CSS carries a "420ms" motion token that a
        # substring match would collide with.
        self.assertIn('420 points', resp.content.decode())

    def test_other_customer_does_not_see_first_customers_points(self):
        # Bob has zero points — Alice's balance must not appear on his page.
        self.client.force_login(self.bob)
        resp = self.client.get('/account/points/')
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode()
        self.assertIn('0 points', body)
        self.assertNotIn('420 points', body)
