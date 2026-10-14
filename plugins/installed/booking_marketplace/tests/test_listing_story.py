"""The product's web story shows on the experience page, as it does on a product page."""

from __future__ import annotations

from decimal import Decimal

from django.test import TestCase
from djmoney.money import Money

from plugins.installed.booking_marketplace.models import BookableService
from plugins.installed.booking_marketplace.products import ensure_product
from plugins.installed.booking_marketplace.tests._theme import MontenegroThemeMixin
from plugins.installed.catalog.models import Vendor


class ListingStoryTests(TestCase):
    def setUp(self):
        vendor = Vendor.objects.create(name='Makers', slug='makers', is_active=True)
        self.svc = BookableService.objects.create(
            vendor=vendor,
            name='Kayak the bay',
            slug='kayak-the-bay',
            listing_kind='experience',
            price=Money(Decimal('50'), 'EUR'),
            is_active=True,
            description='Paddle the bay.',
        )
        self.product = ensure_product(self.svc)

    def _story(self, published=True):
        from plugins.installed.webstories.models import WebStory

        return WebStory.objects.create(
            product=self.product,
            panels=[{'kind': 'cover'}, {'kind': 'text'}],
            is_published=published,
        )

    def _page(self):
        return self.client.get(f'/bookings/{self.svc.slug}/').content.decode()

    def test_a_published_story_shows_on_the_booking_page(self):
        self._story()
        html = self._page()
        self.assertIn('<amp-story-player', html)
        self.assertIn(f'/story/{self.product.slug}/', html)

    def test_no_story_or_an_unpublished_one_shows_nothing(self):
        self.assertNotIn('<amp-story-player', self._page())
        self._story(published=False)
        self.assertNotIn('<amp-story-player', self._page())


class MontenegroListingStoryTests(MontenegroThemeMixin, ListingStoryTests):
    """The Montenegro theme overrides the booking page; it must emit the slot too."""
