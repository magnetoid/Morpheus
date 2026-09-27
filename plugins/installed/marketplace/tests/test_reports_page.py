"""The marketplace Reports page must render.

Its "paid in period" figure filtered VendorPayout on `created_at`, a column the
model has never had (it records `requested_at` and `paid_at`), so the page
raised FieldError on every load.
"""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from djmoney.money import Money


class MarketplaceReportsPageTests(TestCase):
    def test_reports_page_renders_and_counts_payouts_paid_in_the_period(self):
        from plugins.installed.catalog.models import Vendor
        from plugins.installed.marketplace.models import VendorPayout

        vendor = Vendor.objects.create(name='Probe Vendor', slug='probe-vendor')
        VendorPayout.objects.create(
            vendor=vendor,
            amount=Money(Decimal('40.00'), 'USD'),
            status='paid',
            paid_at=timezone.now(),
        )
        staff = get_user_model().objects.create_user(
            username='mkt-staff', email='mkt@x.test', password='pw', is_staff=True
        )
        self.client.force_login(staff)

        resp = self.client.get('/dashboard/apps/marketplace/reports/')

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['summary']['paid_period'], Decimal('40.00'))
