"""Marketplace listings in the dashboard: a list, an editor, and the storefront's Edit link.

Every experience and local good a marketplace store sells is a listing, and the
dashboard had no page for them: the owner saw the store's goods nowhere in the
backend, and the staff bar's Edit led to the host's editor on the storefront
(Montenegro, 2026-10-14). Linda reaches them through listings.search/update.
"""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from djmoney.money import Money

from plugins.installed.booking_marketplace.models import BookableService

LIST = '/dashboard/apps/booking_marketplace/listings/'


class DashboardListingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from plugins.installed.catalog.models import Vendor

        U = get_user_model()
        cls.owner = U.objects.create_superuser('boss', 'boss@example.com', 'x')
        cls.vendor = Vendor.objects.create(name='Makers', slug='makers', is_active=True)
        cls.tour = BookableService.objects.create(
            vendor=cls.vendor,
            name='Kayak the bay',
            slug='kayak-the-bay',
            listing_kind='experience',
            price=Money(Decimal('50'), 'EUR'),
            is_active=True,
        )
        cls.wine = BookableService.objects.create(
            vendor=cls.vendor,
            name='Vranac Reserve',
            slug='vranac-reserve',
            listing_kind='product',
            price=Money(Decimal('18'), 'EUR'),
            is_active=True,
        )

    def setUp(self):
        self.client.force_login(self.owner)

    def _edit(self, svc):
        return f'/dashboard/listings/{svc.pk}/edit/'

    def test_the_list_shows_every_kind_and_filters_by_kind(self):
        page = self.client.get(LIST)
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'Kayak the bay')
        self.assertContains(page, 'Vranac Reserve')
        goods = self.client.get(LIST + '?kind=product')
        self.assertContains(goods, 'Vranac Reserve')
        self.assertNotContains(goods, 'Kayak the bay')

    def test_the_editor_saves_a_listing(self):
        self.assertEqual(self.client.get(self._edit(self.tour)).status_code, 200)
        resp = self.client.post(
            self._edit(self.tour),
            {
                'name': 'Kayak the Bay of Kotor',
                'slug': 'kayak-the-bay',
                'listing_kind': 'experience',
                'vendor': self.vendor.pk,
                'price': '55.00',
                'original_price': '',
                'duration_minutes': '180',
                'duration_label': '3 hours',
                'highlights': 'Sea caves\nBlue Cave swim',
                'languages': 'English, Montenegrin',
                'is_active': 'on',
            },
        )
        self.assertEqual(resp.status_code, 302)
        self.tour.refresh_from_db()
        self.assertEqual(self.tour.name, 'Kayak the Bay of Kotor')
        self.assertEqual(self.tour.price.amount, Decimal('55.00'))
        self.assertEqual(self.tour.highlights, ['Sea caves', 'Blue Cave swim'])
        self.assertEqual(self.tour.languages, ['English', 'Montenegrin'])

    def test_a_new_listing_can_be_created_for_a_host(self):
        resp = self.client.post(
            '/dashboard/listings/new/',
            {
                'name': 'Wild Mountain Honey',
                'slug': '',
                'listing_kind': 'product',
                'vendor': self.vendor.pk,
                'price': '12',
                'duration_minutes': '0',
                'is_active': 'on',
            },
        )
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(BookableService.objects.filter(slug='wild-mountain-honey').exists())

    def test_the_storefront_edit_link_opens_the_dashboard_editor(self):
        page = self.client.get(f'/bookings/{self.tour.slug}/')
        self.assertEqual(page.context['active_edit_url'], self._edit(self.tour))

    def test_a_linked_listing_edit_link_opens_the_product_editor(self):
        from plugins.installed.booking_marketplace.products import ensure_product

        product = ensure_product(self.tour)
        page = self.client.get(f'/bookings/{self.tour.slug}/')
        self.assertEqual(page.context['active_edit_url'], f'/dashboard/products/{product.pk}/')

    def test_a_visitor_cannot_open_them(self):
        self.client.logout()
        self.assertNotEqual(self.client.get(LIST).status_code, 200)
        self.assertNotEqual(self.client.get(self._edit(self.tour)).status_code, 200)


class ListingToolsTests(TestCase):
    def test_linda_can_find_and_change_a_listing_and_a_change_needs_a_yes(self):
        from plugins.installed.booking_marketplace.agent_tools import (
            listings_search_tool,
            listings_update_tool,
        )
        from plugins.installed.catalog.models import Vendor

        vendor = Vendor.objects.create(name='Makers', slug='makers', is_active=True)
        BookableService.objects.create(
            vendor=vendor,
            name='Vranac Reserve',
            slug='vranac-reserve',
            listing_kind='product',
            price=Money(Decimal('18'), 'EUR'),
            is_active=True,
        )
        found = listings_search_tool.handler(q='vranac').output
        self.assertEqual(found['listings'][0]['slug'], 'vranac-reserve')
        self.assertTrue(listings_update_tool.requires_approval)
        listings_update_tool.handler(slug='vranac-reserve', price='19.50', is_active=False)
        svc = BookableService.objects.get(slug='vranac-reserve')
        self.assertEqual(svc.price.amount, Decimal('19.50'))
        self.assertFalse(svc.is_active)

    def test_a_tool_change_reaches_the_listings_product(self):
        from plugins.installed.booking_marketplace.agent_tools import listings_update_tool
        from plugins.installed.booking_marketplace.products import ensure_product
        from plugins.installed.catalog.models import Vendor

        vendor = Vendor.objects.create(name='Makers', slug='makers', is_active=True)
        svc = BookableService.objects.create(
            vendor=vendor,
            name='Vranac Reserve',
            slug='vranac-reserve',
            listing_kind='product',
            price=Money(Decimal('18'), 'EUR'),
            is_active=True,
        )
        product = ensure_product(svc)
        listings_update_tool.handler(slug='vranac-reserve', price='19.50', is_active=False)
        product.refresh_from_db()
        self.assertEqual((product.price.amount, product.status), (Decimal('19.50'), 'draft'))
