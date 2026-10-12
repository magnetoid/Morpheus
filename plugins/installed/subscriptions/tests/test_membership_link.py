"""The Membership link appears only when there is a plan to join.

Every store's footer linked /membership/, which on all four live stores said
"No membership plans are available right now" and was indexable: a soft 404
in every page's footer (found 2026-10-12). The link now shows once an active
plan exists, and the empty page is `noindex`.
"""

from __future__ import annotations

from decimal import Decimal

from django.core.cache import cache
from django.test import TestCase
from djmoney.money import Money

from plugins.installed.subscriptions.models import Plan


class MembershipLinkTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_no_plan_no_link_and_the_empty_page_is_not_indexed(self):
        self.assertNotIn('href="/membership/"', self.client.get('/').content.decode())
        page = self.client.get('/membership/').content.decode()
        self.assertRegex(page, r'<meta name="robots" content="noindex')

    def test_an_active_plan_brings_the_link(self):
        Plan.objects.create(name='Members', slug='members', price=Money(Decimal('5.00'), 'USD'))
        self.assertIn('href="/membership/"', self.client.get('/').content.decode())
