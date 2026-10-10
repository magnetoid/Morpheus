"""Payout and attribution rules come from the program, and defaults from the
settings panel — in the code, not only in the copy.

The affiliate page computed a minimum-payout threshold only to decide whether
to show the button; a POST below it was paid. The referral cookie was hardcoded
to 30 days while programs advertise their own window. And the three keys on
Settings → Marketing → Affiliates ("New AffiliateProgram rows inherit these
defaults") were read by nothing.
"""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from djmoney.money import Money

from plugins.installed.affiliates.models import (
    Affiliate,
    AffiliateConversion,
    AffiliateLink,
    AffiliateProgram,
)
from plugins.installed.affiliates.services import (
    min_payout_threshold,
    program_defaults,
    request_affiliate_payout,
)
from plugins.installed.orders.models import Order


class _Base(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create(email='aff@example.com')
        self.program = AffiliateProgram.objects.create(
            name='Default',
            slug='default',
            commission_type='percent',
            commission_value=Decimal('10'),
            cookie_window_days=90,
            minimum_payout=Money(50, 'USD'),
        )
        self.affiliate = Affiliate.objects.create(
            program=self.program, user=self.user, handle='affone', status='approved'
        )
        self.link = AffiliateLink.objects.create(
            affiliate=self.affiliate, code='abc', landing_url='/'
        )

    def _earn(self, amount):
        order = Order.objects.create(
            email=f'b{AffiliateConversion.objects.count()}@example.com',
            subtotal=Money(amount, 'USD'),
            total=Money(amount, 'USD'),
        )
        return AffiliateConversion.objects.create(
            affiliate=self.affiliate,
            link=self.link,
            order=order,
            commission=Money(amount, 'USD'),
            status='approved',
        )


class PayoutThresholdTests(_Base):
    def test_below_the_program_minimum_is_refused(self):
        self._earn(20)
        with self.assertRaises(ValueError) as ctx:
            request_affiliate_payout(self.affiliate)
        self.assertIn('minimum', str(ctx.exception).lower())

    def test_at_the_minimum_is_paid(self):
        self._earn(30)
        self._earn(20)
        payout = request_affiliate_payout(self.affiliate)
        self.assertEqual(payout.amount, Money(50, 'USD'))

    def test_threshold_falls_back_to_the_settings_panel(self):
        from plugins.registry import app_registry

        self.program.minimum_payout = Money(0, 'USD')
        self.program.save(update_fields=['minimum_payout'])
        plugin = app_registry.get('affiliates')
        original = plugin.get_config_value('min_payout_threshold', 25)
        plugin.set_config('min_payout_threshold', 40)
        try:
            self.assertEqual(min_payout_threshold(self.affiliate), Money(40, 'USD'))
        finally:
            plugin.set_config('min_payout_threshold', original)


class CookieWindowTests(_Base):
    def test_the_cookie_lives_as_long_as_the_program_says(self):
        r = self.client.get('/r/abc')
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.cookies['morph_aff']['max-age'], 90 * 86400)


class ProgramDefaultsTests(_Base):
    def test_defaults_come_from_the_settings_panel(self):
        from plugins.registry import app_registry

        plugin = app_registry.get('affiliates')
        originals = {
            k: plugin.get_config_value(k, None)
            for k in ('default_commission_percent', 'cookie_window_days', 'min_payout_threshold')
        }
        plugin.set_config('default_commission_percent', 12)
        plugin.set_config('cookie_window_days', 45)
        plugin.set_config('min_payout_threshold', 30)
        try:
            self.assertEqual(
                program_defaults(),
                {'commission_value': Decimal('12'), 'cookie_window_days': 45, 'minimum_payout': 30},
            )
        finally:
            for k, v in originals.items():
                plugin.set_config(k, v)

    def test_a_new_program_inherits_them(self):
        from plugins.registry import app_registry

        staff = get_user_model().objects.create_user(
            username='aff-staff', email='s@x.test', password='pw', is_staff=True, is_superuser=True
        )
        self.client.force_login(staff)
        plugin = app_registry.get('affiliates')
        original = plugin.get_config_value('cookie_window_days', None)
        plugin.set_config('cookie_window_days', 45)
        try:
            self.client.post(
                '/dashboard/affiliates/programs/new/', {'action': 'create', 'name': 'Spring push'}
            )
        finally:
            plugin.set_config('cookie_window_days', original)
        program = AffiliateProgram.objects.get(name='Spring push')
        self.assertEqual(program.cookie_window_days, 45)
