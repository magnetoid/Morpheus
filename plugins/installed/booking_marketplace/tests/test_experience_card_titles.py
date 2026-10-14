"""Experience cards lead with the experience's name, at the heading level the page calls for.

The card's heading read "Tivat, Montenegro" with the name in small print below it, and the
whole card was one link, so its link text ran "New · Tivat, Montenegro · A Catamaran Day… ·
€1,190 per person". The name is the title now: an h2 where the grid sits straight under the
page's h1, an h3 inside a section with its own h2, and the title is the card's link, stretched
over the card so the whole card stays clickable.
"""

from __future__ import annotations

import re
from decimal import Decimal

from django.test import TestCase
from djmoney.money import Money

from plugins.installed.booking_marketplace.models import BookableService
from plugins.installed.booking_marketplace.tests._theme import MontenegroThemeMixin
from plugins.installed.catalog.models import Vendor


class ExperienceCardTitleTests(MontenegroThemeMixin, TestCase):
    def setUp(self):
        vendor = Vendor.objects.create(name='Makers', slug='makers', is_active=True)
        common = {
            'vendor': vendor,
            'listing_kind': 'experience',
            'region': 'kotor',
            'location': 'Kotor',
            'price': Money(Decimal('50'), 'EUR'),
            'is_active': True,
        }
        self.kayak = BookableService.objects.create(
            name='Sea Kayaking under the Walls of Kotor', slug='sea-kayak-kotor', **common
        )
        self.walk = BookableService.objects.create(
            name='Kotor Old Town Walk', slug='kotor-old-town-walk', **common
        )

    def _page(self, path):
        resp = self.client.get(path)
        self.assertEqual(resp.status_code, 200, path)
        return resp.content.decode()

    def _title(self, html, level, service):
        name = re.escape(service.name)
        pattern = rf'<{level}[^>]*><a href="/bookings/{service.slug}/" class="card-link">{name}</a></{level}>'
        return re.search(pattern, html)

    def test_the_name_is_the_title_and_the_location_follows(self):
        html = self._page('/bookings/')
        title = self._title(html, 'h2', self.kayak)
        self.assertIsNotNone(title, 'the card title is the name, as a linked h2')
        self.assertIn('Kotor, Montenegro', html[title.end() : title.end() + 1500])

    def test_cards_under_the_page_title_are_h2(self):
        html = self._page('/bookings/')
        self.assertIsNotNone(self._title(html, 'h2', self.walk))
        self.assertIsNone(self._title(html, 'h3', self.walk))

    def test_a_region_pages_cards_are_h2(self):
        # The region page's grid sits straight under its h1 too.
        html = self._page('/regions/kotor/')
        self.assertIsNotNone(self._title(html, 'h2', self.kayak))

    def test_cards_inside_a_section_are_h3(self):
        # "Similar experiences" is an h2 on the booking page; its cards sit below it.
        html = self._page(f'/bookings/{self.kayak.slug}/')
        self.assertIsNotNone(self._title(html, 'h3', self.walk))

    def test_the_card_link_text_is_the_name_alone(self):
        html = self._page('/bookings/')
        links = [
            text.strip()
            for text in re.findall(
                rf'<a href="/bookings/{self.kayak.slug}/"[^>]*>(.*?)</a>', html, re.S
            )
        ]
        self.assertIn(self.kayak.name, links)
        self.assertFalse(any('€' in text or 'Montenegro' in text for text in links), links)
