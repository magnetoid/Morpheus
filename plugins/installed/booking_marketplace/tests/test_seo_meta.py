"""Per-page SEO meta from booking views — titles unique, descriptions real."""

from django.test import TestCase
from djmoney.money import Money

from plugins.installed.booking_marketplace.models import BookableService
from plugins.installed.booking_marketplace.tests._theme import MontenegroThemeMixin
from plugins.installed.catalog.models import Category, Vendor


class ExperienceSeoMetaTests(MontenegroThemeMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        v = Vendor.objects.create(name='Host', slug='host', is_active=True)
        c = Category.objects.create(name='Adventure', slug='adventure')
        cls.svc = BookableService.objects.create(
            vendor=v,
            category=c,
            name='Raft the Tara: Europe’s Deepest Canyon',
            slug='raft-tara',
            short_description='White water in Europe’s deepest canyon.',
            description='Long body.\n\nSecond para.',
            price=Money(80, 'EUR'),
            listing_kind='experience',
            is_active=True,
            location='Žabljak',
        )

    def test_detail_title_is_page_specific(self):
        resp = self.client.get(f'/bookings/{self.svc.slug}/')
        self.assertContains(resp, '<title>Raft the Tara')
        self.assertContains(resp, 'White water in Europe’s deepest canyon.')

    def test_detail_og_is_product(self):
        resp = self.client.get(f'/bookings/{self.svc.slug}/')
        self.assertContains(resp, 'og:type" content="product"')

    def test_list_title_mentions_experiences(self):
        resp = self.client.get('/bookings/')
        self.assertNotContains(resp, '<title>Montenegro Experience</title>')

    def test_category_filtered_list_title_is_category_specific(self):
        resp = self.client.get('/bookings/?category=Adventure')
        self.assertContains(resp, 'Adventure experiences in Montenegro')

    def test_shop_title_is_shop_specific(self):
        resp = self.client.get('/shop/')
        self.assertContains(resp, 'Shop Montenegro')
