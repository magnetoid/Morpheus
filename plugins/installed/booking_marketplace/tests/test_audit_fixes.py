"""Guards for the Sep 2026 SEO/AEO audit findings owned by this plugin."""

from __future__ import annotations

from django.test import TestCase

from plugins.installed.booking_marketplace.tests._theme import MontenegroThemeMixin


def _vendor():
    from plugins.installed.catalog.models import Vendor

    return Vendor.objects.create(name='Local host', slug='local-host', is_active=True)


class LlmsSectionsTests(MontenegroThemeMixin, TestCase):
    """The marketplace catalogue reaches /llms.txt.

    seo enumerates `catalog.Product`; this store's catalogue is
    `BookableService` + `Property`, so the live file shipped a bare
    "## Products" heading with 244 listings invisible beneath it.
    """

    def test_experiences_and_stays_appear(self):
        from djmoney.money import Money

        from plugins.installed.booking_marketplace.models import BookableService, Property
        from plugins.installed.seo.services import render_llms_txt

        vendor = _vendor()
        BookableService.objects.create(
            vendor=vendor,
            name='Bay of Kotor kayak tour',
            slug='kotor-kayak',
            price=Money(45, 'EUR'),
            is_active=True,
        )
        Property.objects.create(
            vendor=vendor,
            name='Villa Perast',
            slug='villa-perast',
            location='Perast',
            is_active=True,
        )

        body = render_llms_txt(full=False)
        self.assertIn('## Experiences', body)
        self.assertIn('/bookings/kotor-kayak/', body)
        self.assertIn('45.00 EUR', body)
        self.assertIn('## Stays', body)
        self.assertIn('/hotels/villa-perast/', body)
        self.assertIn('Perast', body)
        # The double-slash defect the audit counted 45 times.
        self.assertNotIn('.me//', body)
        offenders = [ln for ln in body.splitlines() if '//' in ln.replace('://', ':')]
        self.assertEqual(offenders, [])
