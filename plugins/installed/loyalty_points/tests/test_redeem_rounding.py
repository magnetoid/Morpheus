"""Redemption cap uses FLOOR, not CEIL — no over-redemption at odd rates (#23).

``max_redeemable`` capped point spend with ``amount_to_points`` (ROUND_CEILING —
the "points *needed* to cover an amount" helper). For a cap that is the wrong
direction: at a ``redemption_rate`` that doesn't divide 100 (3, 7, 30…), one
point can be worth MORE than a small order, and the ceil cap let it be redeemed
anyway — the shopper spent a whole point (e.g. worth $0.33 at rate 3) against a
$0.10 order and lost the $0.23 the order didn't use, while the recorded discount
exceeded the order total (breaking ``total = subtotal − discount``).

The cap is now the FLOOR: the most points whose *value* doesn't exceed the order,
so a point worth more than the order can't be over-redeemed. Safe at the default
rate 100 (floor == ceil for any 2-dp total × 100).
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from djmoney.money import Money

from plugins.installed.loyalty_points.models import PointsTransaction
from plugins.installed.loyalty_points.services_redeem import max_redeemable, points_to_amount

_RATE_FN = 'plugins.installed.loyalty_points.services_redeem.redemption_rate'


def _user(balance=100000):
    u = get_user_model().objects.create_user(username='r@e.com', email='r@e.com', password='x')
    PointsTransaction.objects.create(customer=u, points=balance, reason='earn_order')
    return u


class LoyaltyCapRoundingTests(TestCase):
    def setUp(self):
        self.user = _user()

    def _cap(self, rate, total):
        with patch(_RATE_FN, return_value=rate):
            return max_redeemable(self.user, order_total=Money(Decimal(str(total)), 'USD'))

    def test_sub_point_order_at_odd_rate_allows_no_redemption(self):
        # rate 3 → 1 pt is worth $0.33; a $0.10 order must cap at 0 pts, not 1.
        self.assertEqual(self._cap(3, '0.10'), 0)

    def test_odd_rate_exact_multiple(self):
        # rate 3 → 3 pts = $1.00 exactly.
        self.assertEqual(self._cap(3, '1.00'), 3)

    def test_default_rate_cap_unchanged(self):
        # rate 100 (floor == ceil) — regression guard for the common case.
        self.assertEqual(self._cap(100, '2.00'), 200)

    def test_nondivisor_rate_boundary_is_conservatively_undercapped(self):
        # DELIBERATE safe-side trade-off (adversarial-verified): at a rate that
        # doesn't divide 100, the floor cap can refuse the boundary point that
        # would exactly cover the order (rate 3, $0.33 → the 1 pt worth $0.33 is
        # denied → cap 0). This is intentional — the shopper keeps the points and
        # is never mischarged; the alternative (a tight cap) lets points be wasted
        # at high rates. If you make the cap tight, update this test knowingly.
        self.assertEqual(self._cap(3, '0.33'), 0)
        self.assertEqual(self._cap(3, '6.66'), 19)  # 20 would also exactly fit

    def test_capped_points_are_never_worth_more_than_the_order(self):
        # The invariant the fix guarantees: the capped spend's value never
        # exceeds the order. Under the old ceil cap this failed for every rate
        # that doesn't divide 100 (e.g. rate 3, $0.10 → 1 pt worth $0.33).
        for rate in (3, 7, 30, 100):
            for total in ('0.10', '0.33', '0.99', '2.50', '9.99'):
                cap = self._cap(rate, total)
                with patch(_RATE_FN, return_value=rate):
                    worth = points_to_amount(cap, 'USD').amount
                self.assertLessEqual(
                    worth,
                    Decimal(total),
                    msg=f'rate={rate} total={total}: {cap} pts worth {worth} > {total}',
                )
