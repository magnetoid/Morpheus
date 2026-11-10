"""The dashboard's search box finds experiences and stays by name, place or region.

A listing that has its catalog product opens in the product editor, where its
name, text and price are edited (v0.109.0); one without opens the listing form.
"""

from __future__ import annotations

import json

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import resolve
from djmoney.money import Money

from morpheus.core import MorpheusEvents, hook_registry
from plugins import dashboard_search as ds
from plugins.installed.booking_marketplace.models import BookableService
from plugins.installed.catalog.models import Vendor


class ListingSearchTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_superuser(
            username='finder', email='finder@example.com', password='x'
        )
        self.client = Client()
        self.client.force_login(user)
        self.vendor = Vendor.objects.create(name='Host', slug='host', is_active=True)

    def _hits(self, q):
        hits = json.loads(self.client.get('/dashboard/palette/search/', {'q': q}).content)
        return [h for h in hits['hits'] if h['section'] == 'Listings']

    def test_the_app_is_listening(self):
        owners = {e[3] for e in hook_registry._handlers[MorpheusEvents.DASHBOARD_SEARCH]}
        self.assertIn('booking_marketplace', owners)

    def _listing(self, slug, location, product=None):
        return BookableService.objects.create(
            vendor=self.vendor,
            name=slug.replace('-', ' ').title(),
            slug=slug,
            location=location,
            price=Money(50, 'EUR'),
            product=product,
        )

    def test_a_listing_with_its_product_opens_the_product(self):
        from plugins.installed.catalog.models import Product

        product = Product.objects.create(
            name='Kayak at dawn', slug='kayak-at-dawn', price=Money(50, 'EUR')
        )
        self._listing('kayak-at-dawn', 'Zebrafinch bay', product=product)
        urls = [h['url'] for h in self._hits('zebrafinch bay')]
        self.assertEqual(urls, [f'/dashboard/products/{product.pk}/'])
        resolve(urls[0])

    def test_a_listing_without_one_opens_the_listing_form(self):
        listing = self._listing('cave-walk', 'Quillfeather cave')
        urls = [h['url'] for h in self._hits('quillfeather')]
        self.assertEqual(urls, [f'/dashboard/listings/{listing.pk}/edit/'])
        resolve(urls[0])

    def test_the_answer_runs_on_an_empty_store(self):
        for _, handler, _, owner in hook_registry._handlers[MorpheusEvents.DASHBOARD_SEARCH]:
            if owner == 'booking_marketplace':
                self.assertEqual(handler([], query='Čačak', words=ds.words('Čačak')), [])
