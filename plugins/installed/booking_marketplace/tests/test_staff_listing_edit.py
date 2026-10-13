"""Store staff edit any host's listing, and the storefront's staff bar links to it.

A marketplace listing (an experience, a local good) could be edited only in the
host portal, by the host who owns it, so the owner saw no "Edit" in the staff bar on
any listing page (Montenegro, 2026-10-13) and had no way to change one.
"""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from djmoney.money import Money

from plugins.installed.booking_marketplace.models import BookableService


class StaffListingEditTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from plugins.installed.catalog.models import Vendor

        U = get_user_model()
        cls.owner = U.objects.create_superuser('boss', 'boss@example.com', 'x')
        cls.host = U.objects.create_user('host', 'host@example.com', 'x')
        cls.other_host = U.objects.create_user('other', 'other@example.com', 'x')
        cls.visitor = U.objects.create_user('guest', 'guest@example.com', 'x')
        vendor = Vendor.objects.create(name='Makers', slug='makers', is_active=True, owner=cls.host)
        Vendor.objects.create(name='Others', slug='others', is_active=True, owner=cls.other_host)
        cls.svc = BookableService.objects.create(
            vendor=vendor,
            name='Kayak the bay',
            slug='kayak-the-bay',
            listing_kind='experience',
            price=Money(Decimal('50'), 'EUR'),
            is_active=True,
        )

    def _edit_url(self):
        return f'/bookings/host/{self.svc.slug}/edit/'

    def test_staff_open_and_save_any_listing(self):
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(self._edit_url()).status_code, 200)
        resp = self.client.post(
            self._edit_url(),
            {
                'name': 'Kayak the Bay of Kotor',
                'listing_kind': 'experience',
                'price': '55',
                'is_active': 'on',
            },
        )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp['Location'], f'/bookings/{self.svc.slug}/')
        self.svc.refresh_from_db()
        self.assertEqual(self.svc.name, 'Kayak the Bay of Kotor')
        self.assertEqual(self.svc.vendor.slug, 'makers')

    def test_another_host_still_cannot_edit_it(self):
        self.client.force_login(self.other_host)
        self.assertEqual(self.client.get(self._edit_url()).status_code, 404)

    def test_a_visitor_gets_the_become_a_host_page(self):
        self.client.force_login(self.visitor)
        resp = self.client.get(self._edit_url())
        self.assertNotContains(resp, 'name="name"')

    def test_the_listing_page_links_staff_to_the_editor(self):
        self.client.force_login(self.owner)
        page = self.client.get(f'/bookings/{self.svc.slug}/')
        # The owner asked for the dashboard's editor, not the host's (2026-10-14).
        self.assertEqual(
            page.context['active_edit_url'], f'/dashboard/listings/{self.svc.pk}/edit/'
        )
        self.client.logout()
        page = self.client.get(f'/bookings/{self.svc.slug}/')
        self.assertFalse(page.context.get('active_edit_url'))
