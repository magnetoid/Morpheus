"""The travel stores show the trail they mark up (v0.161.0).

`/bookings/`, `/shop/`, `/hotels/`, `/places/`, `/regions/` and `/events/` declared a
BreadcrumbList and showed no trail; the region page's visible trail had no Home. Every
listing and detail page now renders `{% breadcrumb_trail %}` from the same
`breadcrumb_items` the head builds its BreadcrumbList from, in both travel themes (the
croatia theme is a copy of montenegro's, so each is rendered here). The readers are
themes/test_breadcrumb_trail.py's.
"""

from __future__ import annotations

from decimal import Decimal

from django.core.cache import cache
from django.test import TestCase, override_settings
from djmoney.money import Money

from plugins.installed.booking_marketplace.models import BookableService, Event, Place, Property
from plugins.installed.booking_marketplace.tests._i18n import serbian_enabled
from themes.test_breadcrumb_trail import assert_one_trail, visible_trail
from themes.test_head_contract import _activate_theme


def travel_fixtures(region: str) -> None:
    """A host's experience and product, a hotel, a town and its festival in `region`."""
    from plugins.installed.catalog.models import Category, Product, Vendor

    host = Vendor.objects.create(name='Trail Host', slug='trail-host', is_active=True)
    water = Category.objects.create(name='Trail Water', slug='trail-water')
    boats = Category.objects.create(name='Trail Boats', slug='trail-boats', parent=water)
    for slug, kind in (('trail-boat', 'experience'), ('trail-honey', 'product')):
        BookableService.objects.create(
            vendor=host,
            name=slug.replace('-', ' ').title(),
            slug=slug,
            listing_kind=kind,
            region=region,
            category=boats,
            price=Money(Decimal('40'), 'EUR'),
            is_active=True,
        )
    Property.objects.create(
        vendor=host, name='Trail Rooms', slug='trail-rooms', region=region, is_active=True
    )
    place = Place.objects.create(
        name='Trail Town', slug='trail-town', region=region, is_active=True
    )
    Event.objects.create(name='Trail Fest', slug='trail-fest', region=region, place=place, month=7)
    Product.objects.create(
        name='Trail Map',
        slug='trail-map',
        sku='TRAIL-MAP',
        price=Money(Decimal('9'), 'EUR'),
        product_type='simple',
        status='active',
        category=boats,
    )


class _TravelTrailTests:
    theme = ''
    region = ''

    @classmethod
    def setUpTestData(cls):
        travel_fixtures(cls.region)

    def setUp(self):
        cache.clear()
        _activate_theme(self, self.theme)

    def _page(self, path):
        resp = self.client.get(path)
        self.assertEqual(resp.status_code, 200, path)
        return resp.content.decode()

    def test_every_travel_page_shows_the_trail_it_marks_up(self):
        for path in (
            '/bookings/',
            '/shop/',
            '/hotels/',
            '/places/',
            '/regions/',
            '/events/',
            f'/regions/{self.region}/',
            f'/regions/{self.region}/trail-water/',
            '/bookings/trail-boat/',
            '/hotels/trail-rooms/',
            '/places/trail-town/',
            '/events/trail-fest/',
            '/products/trail-map/',
            '/category/trail-boats/',
        ):
            with self.subTest(path=path):
                shown = assert_one_trail(self, self._page(path))
                self.assertEqual(shown[0][1], '/', f'{path}: the trail starts at Home')

    def test_the_region_trail_starts_with_home(self):
        shown = visible_trail(self._page(f'/regions/{self.region}/'))
        self.assertEqual([h for _n, h in shown], ['/', '/regions/', None])

    def test_the_product_page_names_the_category_page(self):
        shown = assert_one_trail(self, self._page('/products/trail-map/'))
        self.assertEqual(
            [h for _n, h in shown[2:]],
            ['/category/trail-water/', '/category/trail-boats/', None],
        )


class MontenegroTrailTests(_TravelTrailTests, TestCase):
    theme = 'montenegro'
    region = 'kotor'


@override_settings(LANGUAGES=[('en', 'English'), ('hr', 'Hrvatski')])
class CroatiaTrailTests(_TravelTrailTests, TestCase):
    theme = 'croatia'
    region = 'split'


@serbian_enabled
class SerbianTrailTests(TestCase):
    """On `/sr/` both renderings stay in the Serbian tree."""

    @classmethod
    def setUpTestData(cls):
        travel_fixtures('kotor')

    def setUp(self):
        cache.clear()
        _activate_theme(self, 'montenegro')

    def test_the_region_trail_stays_serbian(self):
        resp = self.client.get('/sr/regions/kotor/trail-water/')
        self.assertEqual(resp.status_code, 200)
        shown = assert_one_trail(self, resp.content.decode())
        self.assertEqual(
            [h for _n, h in shown],
            ['/sr/', '/sr/regions/', '/sr/regions/kotor/', None],
        )
