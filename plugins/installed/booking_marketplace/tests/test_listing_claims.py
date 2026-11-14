"""A travel listing claims only what is true today (v0.163.0).

- The sitemap carries each detail page's lastmod and photos, and a one-off
  event leaves it once its last day has passed
  (https://developers.google.com/search/docs/crawling-indexing/sitemaps/build-sitemap).
- No Event node once the stored edition is over: Google's event page wants
  events that have not yet ended
  (https://developers.google.com/search/docs/appearance/structured-data/event).
- A hotel with only gallery photos still has an image.
- Descriptions are cut at a sentence or word, never inside one.
"""

from __future__ import annotations

import datetime
import json
import re

from django.test import Client, TestCase

from core.utils.site import store_today
from plugins.installed.booking_marketplace import seo_jsonld
from plugins.installed.booking_marketplace.models import (
    Event,
    Place,
    Property,
    PropertyImage,
)
from plugins.installed.booking_marketplace.sitemap import contribute_sitemap_urls

_DAY = datetime.timedelta(days=1)
_LONG = (
    'Kotor sits at the end of a fjord-like bay under limestone walls that climb '
    'twelve hundred steps to the fortress of San Giovanni, and its old town is a '
    'maze of squares, churches and cats where every lane ends at another gate '
    'facing the water and the mountains beyond it.'
)


def _vendor():
    from plugins.installed.catalog.models import Vendor

    return Vendor.objects.create(name='Claims Vendor', slug='claims-vendor', is_active=True)


def _event(slug, **kw):
    defaults = {'name': slug.title(), 'slug': slug, 'month': 7, 'is_active': True}
    return Event.objects.create(**{**defaults, **kw})


def _entry(slug_path):
    return next(
        (e for e in contribute_sitemap_urls([]) if e['loc'].endswith(slug_path)),
        None,
    )


class SitemapClaimsTests(TestCase):
    def test_a_place_carries_its_date_and_photo(self):
        place = Place.objects.create(
            name='Kotor', slug='kotor-claims', is_active=True, image='places/kotor.jpg'
        )
        entry = _entry('/places/kotor-claims/')
        self.assertEqual(entry['lastmod'], place.updated_at)
        self.assertEqual(len(entry['images']), 1)
        self.assertTrue(entry['images'][0].startswith('http'))
        self.assertTrue(entry['images'][0].endswith('places/kotor.jpg'))

    def test_a_row_nobody_saved_since_claims_no_date(self):
        Place.objects.create(name='Budva', slug='budva-claims', is_active=True)
        Place.objects.filter(slug='budva-claims').update(updated_at=None)
        entry = _entry('/places/budva-claims/')
        self.assertIsNone(entry['lastmod'])
        self.assertNotIn('images', entry)

    def test_a_stay_lists_its_cover_and_gallery(self):
        prop = Property.objects.create(
            vendor=_vendor(), name='Hotel', slug='hotel-claims', is_active=True
        )
        for n in range(8):
            PropertyImage.objects.create(property=prop, image=f'properties/gallery/{n}.jpg')
        entry = _entry('/hotels/hotel-claims/')
        self.assertEqual(entry['lastmod'], prop.updated_at)
        self.assertEqual(len(entry['images']), 6)

    def test_an_ended_one_off_event_leaves_and_annual_or_undated_stay(self):
        today = store_today()
        _event(
            'past-one-off',
            start_date=today - 10 * _DAY,
            end_date=today - 8 * _DAY,
            is_annual=False,
        )
        _event('past-annual', start_date=today - 10 * _DAY, is_annual=True)
        _event('undated', start_date=None)
        _event('ends-today', start_date=today - 2 * _DAY, end_date=today, is_annual=False)
        self.assertIsNone(_entry('/events/past-one-off/'))
        for slug in ('past-annual', 'undated', 'ends-today'):
            with self.subTest(slug=slug):
                self.assertIsNotNone(_entry(f'/events/{slug}/'))


class EventNodeTests(TestCase):
    def _types(self, slug):
        body = Client().get(f'/events/{slug}/').content.decode()
        blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>', body, re.S)
        return [n.get('@type') for n in json.loads(blocks[0])['@graph']]

    def test_no_node_once_the_edition_is_over(self):
        today = store_today()
        _event('over-claims', start_date=today - 5 * _DAY, end_date=today - _DAY, is_annual=False)
        self.assertNotIn('Event', self._types('over-claims'))

    def test_an_annual_events_past_date_is_that_editions(self):
        _event('annual-claims', start_date=store_today() - 30 * _DAY, is_annual=True)
        self.assertNotIn('Event', self._types('annual-claims'))

    def test_a_coming_or_running_event_keeps_its_node(self):
        today = store_today()
        _event('running-claims', start_date=today - _DAY, end_date=today + _DAY, is_annual=False)
        _event('coming-claims', start_date=today + 30 * _DAY, is_annual=True)
        self.assertIn('Event', self._types('running-claims'))
        self.assertIn('Event', self._types('coming-claims'))


class HotelImageTests(TestCase):
    def test_the_first_gallery_photo_when_there_is_no_cover(self):
        prop = Property.objects.create(
            vendor=_vendor(), name='Gallery Hotel', slug='gallery-hotel', is_active=True
        )
        PropertyImage.objects.create(
            property=prop, image='properties/gallery/first.jpg', sort_order=0
        )
        PropertyImage.objects.create(
            property=prop, image='properties/gallery/second.jpg', sort_order=1
        )
        node = seo_jsonld.property_nodes(prop, url='https://shop.test/hotels/gallery-hotel/')[0]
        self.assertTrue(node['image'].endswith('properties/gallery/first.jpg'))

    def test_no_photo_no_image(self):
        prop = Property.objects.create(
            vendor=_vendor(), name='Bare Hotel', slug='bare-hotel', is_active=True
        )
        node = seo_jsonld.property_nodes(prop, url='https://shop.test/hotels/bare-hotel/')[0]
        self.assertNotIn('image', node)


class DescriptionCutTests(TestCase):
    def _ends_on_a_word(self, text, source):
        self.assertTrue(text)
        last = text.rstrip('…').rstrip(' .,;').split()[-1]
        self.assertIn(last, [w.strip('.,;') for w in source.split()])

    def test_a_place_description_is_cut_on_a_word(self):
        from plugins.installed.booking_marketplace.views import _place_meta_description

        place = Place(name='Kotor', slug='kotor-cut', overview=f'<p>{_LONG}</p>')
        desc = _place_meta_description(place)
        self.assertLessEqual(len(desc), 158)
        self.assertNotIn('<p>', desc)
        self._ends_on_a_word(desc, _LONG)

    def test_the_destination_node_is_cut_on_a_word(self):
        place = Place.objects.create(
            name='Kotor', slug='kotor-node', overview=(_LONG + ' ') * 3, is_active=True
        )
        node = seo_jsonld.place_nodes(place, url='https://shop.test/places/kotor-node/')[0]
        self.assertLessEqual(len(node['description']), 300)
        self._ends_on_a_word(node['description'], _LONG)

    def test_the_hotel_page_description_is_cut_on_a_word(self):
        prop = Property.objects.create(
            vendor=_vendor(),
            name='Cut Hotel',
            slug='cut-hotel',
            description=_LONG,
            is_active=True,
        )
        response = Client().get(f'/hotels/{prop.slug}/')
        self.assertEqual(response.status_code, 200)
        desc = response.context['seo_description']
        self.assertLessEqual(len(desc), 155)
        self._ends_on_a_word(desc, _LONG)
