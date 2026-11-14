"""The head contract on the travel stores' own page kinds, under both travel themes.

`themes/test_head_contract.py` renders the shop page kinds under every contract
theme; it cannot render an experience, a hotel, a place, an event or a region page
without this app, so those are checked here, under montenegro AND croatia (the
croatia theme is a copy of montenegro's, so a fix to one is not in the other).

Each page: one `<title>`, one canonical, one robots meta, one JSON-LD block in the
whole document and it is the head's graph, one `og:title`, and no hardcoded shop
name in the title. The journal, about and contact templates of both themes called
`{% seo_article_jsonld %}`, `{% seo_aboutpage_jsonld %}` and
`{% seo_contactpage_jsonld %}` with "Montenegro Experience" written into them
until v0.164.0; the head contract silenced them, and only a render shows that.
"""

from __future__ import annotations

import re
from decimal import Decimal

from django.core.cache import cache
from django.test import TestCase
from djmoney.money import Money

from plugins.installed.booking_marketplace.models import BookableService, Event, Place, Property
from themes.registry import theme_registry
from themes.test_head_contract import _activate_theme, assert_one_graph, theme_brand

_TITLE = re.compile(r'<title[^>]*>(.*?)</title>', re.I | re.S)
_CANONICAL = re.compile(r'<link[^>]+rel=["\']canonical["\']', re.I)
_ROBOTS = re.compile(r'<meta[^>]+name=["\']robots["\'][^>]+content=["\']([^"\']*)', re.I)

# A region each theme's country has (booking_marketplace/country.py).
_REGION = {'montenegro': 'kotor', 'croatia': 'istria'}


class TravelHeadContractTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from plugins.installed.catalog.models import Category, Vendor

        host = Vendor.objects.create(name='Contract Host', slug='contract-host', is_active=True)
        tours = Category.objects.create(name='Contract Tours', slug='contract-tours')
        for region in _REGION.values():
            BookableService.objects.create(
                vendor=host,
                category=tours,
                name=f'Contract boat trip {region}',
                slug=f'contract-boat-{region}',
                short_description='A morning on the water.',
                description='<p>Three hours on the water with a local skipper.</p>',
                price=Money(Decimal('45'), 'EUR'),
                listing_kind='experience',
                region=region,
                is_active=True,
            )
            Property.objects.create(
                vendor=host,
                name=f'Contract Rooms {region}',
                slug=f'contract-rooms-{region}',
                property_type='hotel',
                region=region,
                location='Old town',
                price_from=Money(Decimal('90'), 'EUR'),
                is_active=True,
            )
            place = Place.objects.create(
                name=f'Contract Town {region}',
                slug=f'contract-town-{region}',
                region=region,
                summary='A small town on the bay.',
                is_active=True,
            )
            Event.objects.create(
                name=f'Contract Night {region}',
                slug=f'contract-night-{region}',
                place=place,
                month=8,
                when_label='Mid-August',
                summary='Music on the waterfront.',
                is_active=True,
            )

    def _pages(self, region: str) -> tuple[str, ...]:
        return (
            f'/bookings/contract-boat-{region}/',
            f'/hotels/contract-rooms-{region}/',
            f'/places/contract-town-{region}/',
            f'/events/contract-night-{region}/',
            f'/regions/{region}/',
        )

    def test_each_travel_page_carries_one_head(self):
        checked = []
        for name, region in sorted(_REGION.items()):
            _activate_theme(self, name)
            brand = re.compile(re.escape(theme_brand(theme_registry.get(name))), re.I)
            for path in self._pages(region):
                with self.subTest(theme=name, path=path):
                    cache.clear()
                    response = self.client.get(path)
                    self.assertEqual(response.status_code, 200, path)
                    body = response.content.decode()
                    titles = _TITLE.findall(body)
                    self.assertEqual(len(titles), 1, f'{path}: <title> count')
                    self.assertEqual(len(_CANONICAL.findall(body)), 1, f'{path}: canonical')
                    robots = _ROBOTS.findall(body)
                    self.assertEqual(len(robots), 1, f'{path}: robots meta count')
                    self.assertNotIn('noindex', robots[0], f'{path} should be indexable')
                    assert_one_graph(self, body, f'{name} {path}')
                    self.assertIsNone(
                        brand.search(titles[0]),
                        f'{name}{path}: the theme hardcodes the brand: {titles[0]!r}',
                    )
                    checked.append((name, path))
        self.assertEqual(len(checked), 10)
