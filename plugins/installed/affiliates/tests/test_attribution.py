"""Affiliate attribution and payout tests."""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from djmoney.money import Money

from plugins.installed.affiliates.models import (
    Affiliate,
    AffiliateLink,
    AffiliateProgram,
)
from plugins.installed.affiliates.services import (
    attribute_order,
    record_click,
)
from plugins.installed.orders.models import Order

Customer = get_user_model()


class AffiliateAttributionTests(TestCase):
    def setUp(self) -> None:
        self.user = Customer.objects.create(email='aff@example.com')
        self.program = AffiliateProgram.objects.create(
            name='Default',
            slug='default',
            commission_type='percent',
            commission_value=Decimal('10'),
        )
        self.affiliate = Affiliate.objects.create(
            program=self.program,
            user=self.user,
            handle='affone',
            status='approved',
        )
        self.link = AffiliateLink.objects.create(
            affiliate=self.affiliate,
            code='abc',
            landing_url='/',
        )
        self.order = Order.objects.create(
            email='buyer@example.com',
            subtotal=Money(100, 'USD'),
            total=Money(100, 'USD'),
        )

    def test_record_click_increments_count(self):
        record_click(code='abc', referer='', user_agent='ua')
        self.link.refresh_from_db()
        self.assertEqual(self.link.click_count, 1)

    def test_attribute_order_creates_conversion(self):
        # attribute_order now requires a click within the cookie window before
        # crediting a conversion — record one first.
        record_click(code='abc', referer='', user_agent='ua')
        conv = attribute_order(order=self.order, affiliate_code='abc')
        self.assertIsNotNone(conv)
        self.assertEqual(conv.commission, Money(Decimal('10.00'), 'USD'))
        self.assertEqual(conv.status, 'pending')

    def test_attribute_skips_unapproved_affiliate(self):
        self.affiliate.status = 'pending'
        self.affiliate.save()
        self.assertIsNone(attribute_order(order=self.order, affiliate_code='abc'))

    def test_unknown_code_is_noop(self):
        self.assertIsNone(attribute_order(order=self.order, affiliate_code='nope'))
