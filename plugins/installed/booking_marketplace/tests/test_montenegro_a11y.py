"""Montenegro's pages name every control and nav, and skip no heading level.

The live axe audit found the experience page's date, time and guests fields
read out with no name, two unnamed ``<nav>`` on one page, and the footer's
titles one level too deep (``h4`` under the page's ``h2``). The readers are the
ones the other themes are checked with (``themes/test_a11y_markup.py``).
"""

from __future__ import annotations

from decimal import Decimal

from django.test import TestCase
from djmoney.money import Money

from plugins.installed.booking_marketplace.models import BookableService
from plugins.installed.booking_marketplace.products import ensure_product
from plugins.installed.booking_marketplace.tests._theme import MontenegroThemeMixin
from plugins.installed.catalog.models import Vendor
from themes.test_a11y_markup import heading_skips, unlabelled_controls, unnamed_navs


class MontenegroA11yTests(MontenegroThemeMixin, TestCase):
    def setUp(self):
        vendor = Vendor.objects.create(name='Makers', slug='makers', is_active=True)
        self.svc = BookableService.objects.create(
            vendor=vendor,
            name='Kayak the bay',
            slug='kayak-the-bay',
            listing_kind='experience',
            region='kotor',
            location='Kotor',
            price=Money(Decimal('50'), 'EUR'),
            is_active=True,
            short_description='Two calm hours paddling under the walls of Kotor.',
            description='Paddle the bay.',
            max_guests_per_booking=8,
        )
        ensure_product(self.svc)

    def test_pages(self):
        for path in ('/', '/bookings/', f'/bookings/{self.svc.slug}/', '/hotels/'):
            with self.subTest(path=path):
                resp = self.client.get(path, follow=True)
                self.assertEqual(resp.status_code, 200, path)
                body = resp.content.decode()
                self.assertEqual(heading_skips(body), [], f'{path}: heading order')
                self.assertEqual(unlabelled_controls(body), [], f'{path}: unlabelled control')
                self.assertLessEqual(len(unnamed_navs(body)), 1, f'{path}: navs without a name')

    def test_the_booking_form_names_its_fields(self):
        body = self.client.get(f'/bookings/{self.svc.slug}/').content.decode()
        self.assertIn('name="booking_date"', body, 'booking form did not render — fixture drift')
        self.assertIn('name="guests"', body)
