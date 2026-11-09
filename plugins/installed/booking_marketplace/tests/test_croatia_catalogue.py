"""Croatia Experience's catalogue and the hotels that list no rooms (Nov 2026).

croatia-experience.me opened empty. `manage.py seed_croatia` fills it from
`seed_data/croatia/` under the owner's rules (docs/plans/croatia-catalogue-2026-11.md):
- real places, hotels and events;
- experiences hosted by the store itself;
- no reviews, ratings, "was" prices or bestseller flags;
- hotels with no rooms or rates.

A hotel with no rooms used to show "from €0.00 / night" and a Rooms section with no form.
Now it says "Contact for price" and takes an enquiry.

Places and experiences carry a free Wikimedia Commons photo, and its page names the
author and licence. The photo replaces only a bundled stand-in cover, never one someone
uploaded.
"""

from __future__ import annotations

import io
import re
import shutil
import tempfile
from io import StringIO
from pathlib import Path
from unittest import mock

from django.core.files.base import ContentFile
from django.core.management import CommandError, call_command
from django.db import models
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils.html import escape
from PIL import Image

from plugins.installed.booking_marketplace import country
from plugins.installed.booking_marketplace.management.commands import seed_croatia
from plugins.installed.booking_marketplace.models import (
    EVENT_CATEGORIES,
    PLACE_TYPES,
    PROPERTY_TYPES,
    BookableService,
    Event,
    Place,
    Property,
    ServiceReview,
    StayEnquiry,
)
from plugins.installed.booking_marketplace.seed_data import croatia as data
from themes.test_head_contract import _activate_theme

REGIONS = {key for key, _ in country.CROATIA.regions}
SLUG = re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*$')
SEED_ASSETS = Path(seed_croatia.SEED_DIR)


FREE_LICENCE = re.compile(r'^(CC0|Public domain|CC BY(-SA)? \d\.\d( [a-z]{2})?)$')


def _jpeg(colour=(20, 120, 200)) -> bytes:
    buf = io.BytesIO()
    Image.new('RGB', (8, 6), colour).save(buf, 'JPEG')
    return buf.getvalue()


def _in_croatia(lat, lon) -> bool:
    return 42.3 <= float(lat) <= 46.6 and 13.4 <= float(lon) <= 19.5


class _FieldLimits:
    def assertFits(self, model, row: dict, label: str):
        """Every text value fits the model column it is written to."""
        for key, value in row.items():
            try:
                field = model._meta.get_field(key)
            except Exception:  # noqa: BLE001 — a data-only key (featured, place_slug, image)
                continue
            if isinstance(field, models.CharField) and isinstance(value, str):
                self.assertLessEqual(
                    len(value), field.max_length, f'{label}: {key} is longer than the column'
                )

    def assertUniqueSlugs(self, rows: list[dict], kind: str):
        slugs = [r['slug'] for r in rows]
        self.assertEqual(len(slugs), len(set(slugs)), f'duplicate {kind} slug')
        for slug in slugs:
            self.assertRegex(slug, SLUG)


class CroatiaDataTests(_FieldLimits, SimpleTestCase):
    def test_places_are_whole_and_in_croatia(self):
        self.assertGreaterEqual(len(data.PLACES), 80)
        self.assertUniqueSlugs(data.PLACES, 'place')
        types = {k for k, _ in PLACE_TYPES}
        for p in data.PLACES:
            label = p['slug']
            self.assertIn(p['region'], REGIONS, label)
            self.assertIn(p['place_type'], types, label)
            self.assertTrue(_in_croatia(p['latitude'], p['longitude']), label)
            for key in ('summary', 'description', 'overview'):
                self.assertTrue(p[key].strip(), f'{label}: empty {key}')
            self.assertTrue(p['faqs'] and all(f['q'] and f['a'] for f in p['faqs']), label)
            self.assertTrue(all(q['label'] and q['value'] for q in p['quick_facts']), label)
            self.assertTrue(all(s['heading'] and s['body'] for s in p['sections']), label)
            for link in p['external_links']:
                self.assertTrue(link['url'].startswith('https://'), label)
            self.assertFits(Place, p, label)

    def test_experiences_are_hosted_by_the_store_and_claim_nothing(self):
        self.assertGreaterEqual(len(data.EXPERIENCES), 80)
        self.assertUniqueSlugs(data.EXPERIENCES, 'experience')
        places = {p['name'] for p in data.PLACES}
        for e in data.EXPERIENCES:
            label = e['slug']
            # The owner's rules: no named host, no rating, no "was" price, no bestseller.
            for key in ('host', 'original_price', 'rating', 'review_count', 'is_bestseller'):
                self.assertNotIn(key, e, label)
            self.assertIn(e['category'], seed_croatia.CATEGORIES, label)
            self.assertIn(e['region'], REGIONS, label)
            self.assertIn(e['location'], places, f'{label}: location names no place')
            self.assertIsInstance(e['price'], int, label)
            self.assertGreater(e['price'], 0, label)
            self.assertGreater(e['duration_minutes'], 0, label)
            self.assertTrue(_in_croatia(e['latitude'], e['longitude']), label)
            if e.get('image'):
                self.assertTrue((SEED_ASSETS / e['image']).exists(), label)
            self.assertFits(BookableService, e, label)

    def test_hotels_are_real_names_without_rooms_or_rates(self):
        self.assertGreaterEqual(len(data.HOTELS), 100)
        self.assertUniqueSlugs(data.HOTELS, 'hotel')
        types = {k for k, _ in PROPERTY_TYPES}
        for h in data.HOTELS:
            label = h['slug']
            for key in ('price', 'price_from', 'rooms', 'rating', 'review_count', 'amenities'):
                self.assertNotIn(key, h, label)
            self.assertIn(h['property_type'], types, label)
            self.assertIn(h['star_rating'], range(6), label)
            self.assertIn(h['region'], REGIONS, label)
            self.assertTrue(h['description'].strip(), label)
            self.assertFits(Property, h, label)

    def test_every_photo_is_free_and_credited(self):
        rows = data.PLACES + data.EXPERIENCES
        with_photo = [r for r in rows if r.get('photo')]
        self.assertGreaterEqual(len(with_photo), len(rows) * 0.9)
        files = [r['photo']['source_url'] for r in with_photo]
        self.assertEqual(len(files), len(set(files)), 'two rows share a photo')
        for r in with_photo:
            photo, label = r['photo'], r['slug']
            self.assertTrue(photo['src'].startswith(seed_croatia.PHOTO_HOST), label)
            self.assertTrue(
                photo['source_url'].startswith('https://commons.wikimedia.org/wiki/File:'), label
            )
            self.assertRegex(photo['licence'], FREE_LICENCE, label)
            self.assertTrue(photo['author'].strip(), label)
            if photo['licence'].startswith('CC BY'):
                self.assertTrue(photo['licence_url'].startswith('https://'), label)

    def test_events_point_at_seeded_places(self):
        self.assertUniqueSlugs(data.EVENTS, 'event')
        places = {p['slug'] for p in data.PLACES}
        categories = {k for k, _ in EVENT_CATEGORIES}
        for e in data.EVENTS:
            label = e['slug']
            self.assertIn(e['category'], categories, label)
            self.assertIn(e['region'], REGIONS, label)
            self.assertIn(e['month'], range(1, 13), label)
            if e['place_slug']:
                self.assertIn(e['place_slug'], places, label)
            if e.get('official_url'):
                self.assertTrue(e['official_url'].startswith('https://'), label)
            self.assertFits(Event, e, label)


def _sample(rows, n=2):
    return list(rows[:n])


class _SeedFixture:
    """The data cut to a sample, media in a temp dir, downloads faked."""

    def setUp(self):
        media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, media, ignore_errors=True)
        override = override_settings(MEDIA_ROOT=media)
        override.enable()
        self.addCleanup(override.disable)
        event = dict(data.EVENTS[0], place_slug=data.PLACES[0]['slug'])
        for name, rows in (
            ('PLACES', _sample(data.PLACES)),
            ('EXPERIENCES', _sample(data.EXPERIENCES)),
            ('HOTELS', _sample(data.HOTELS)),
            ('EVENTS', [event]),
        ):
            patcher = mock.patch.object(data, name, rows)
            patcher.start()
            self.addCleanup(patcher.stop)
        # Never the network: every photo "downloads" as this small JPEG.
        self.photo = _jpeg()
        downloader = mock.patch.object(seed_croatia, '_download', return_value=self.photo)
        self.download = downloader.start()
        self.addCleanup(downloader.stop)

    def _run(self) -> str:
        out = StringIO()
        call_command('seed_croatia', stdout=out)
        return out.getvalue()


class SeedCroatiaTests(_SeedFixture, TestCase):
    def test_it_refuses_a_store_that_is_not_croatian(self):
        _activate_theme(self, 'montenegro')
        with self.assertRaises(CommandError):
            self._run()
        self.assertFalse(Place.objects.exists())

    def test_it_fills_a_croatian_store_once(self):
        _activate_theme(self, 'croatia')
        self._run()
        self.assertEqual(Place.objects.count(), 2)
        self.assertTrue(all(p.image for p in Place.objects.all()))

        services = list(BookableService.objects.select_related('product', 'vendor'))
        self.assertEqual(len(services), 2)
        for s in services:
            self.assertEqual(s.vendor.name, seed_croatia.HOST_NAME)
            self.assertIsNone(s.original_price)
            self.assertFalse(s.is_bestseller)
            self.assertEqual(s.rating, 0)
            # Each listing extends a catalog Product (v0.109).
            self.assertEqual(s.product.product_type, 'service')
            self.assertEqual(s.product.status, 'active')
            self.assertIsNone(s.product.compare_at_price)
        self.assertFalse(ServiceReview.objects.exists())

        for prop in Property.objects.all():
            self.assertEqual(prop.vendor.name, seed_croatia.HOST_NAME)
            self.assertFalse(prop.room_types.exists())
            self.assertEqual(prop.price_from.amount, 0)
        event = Event.objects.get()
        self.assertEqual(event.place.slug, data.PLACES[0]['slug'])

        second = self._run()
        self.assertEqual(second.count(' 0 created'), 4, second)

    def test_a_second_run_keeps_a_dashboard_edit(self):
        _activate_theme(self, 'croatia')
        self._run()
        place = Place.objects.get(slug=data.PLACES[0]['slug'])
        place.summary = 'Edited in the dashboard'
        place.save(update_fields=['summary'])
        self._run()
        place.refresh_from_db()
        self.assertEqual(place.summary, 'Edited in the dashboard')


class SeedPhotoTests(_SeedFixture, TestCase):
    """The Commons photo, its credit, and the stand-in it may replace."""

    def setUp(self):
        super().setUp()
        _activate_theme(self, 'croatia')

    @staticmethod
    def _bytes(fieldfile) -> bytes:
        with fieldfile.storage.open(fieldfile.name, 'rb') as fh:
            return fh.read()

    def test_the_photo_comes_with_its_author_and_licence(self):
        self._run()
        row = data.PLACES[0]
        place = Place.objects.get(slug=row['slug'])
        self.assertEqual(self._bytes(place.image), self.photo)
        self.assertEqual(place.photo_credit['author'], row['photo']['author'])
        self.assertEqual(place.photo_credit['licence'], row['photo']['licence'])

        service = BookableService.objects.get(slug=data.EXPERIENCES[0]['slug'])
        self.assertEqual(self._bytes(service.image), self.photo)
        # The product keeps its own copy, so deleting one never empties the other.
        (copy,) = service.product.images.all()
        self.assertEqual(self._bytes(copy.image), self.photo)
        self.assertNotEqual(copy.image.name, service.image.name)

    def test_a_failed_download_keeps_the_stand_in_until_the_next_run(self):
        self.download.return_value = None
        self._run()
        place = Place.objects.get(slug=data.PLACES[0]['slug'])
        self.assertTrue(seed_croatia._is_stand_in(place.image))
        self.assertIsNone(place.photo_credit)
        stand_in_name = place.image.name

        self.download.return_value = self.photo
        self._run()
        place.refresh_from_db()
        self.assertEqual(self._bytes(place.image), self.photo)
        self.assertIsNotNone(place.photo_credit)
        # A new address: browsers, the CDN and seo's /img/ copies cached the stand-in's.
        self.assertNotEqual(place.image.name, stand_in_name)
        service = BookableService.objects.get(slug=data.EXPERIENCES[0]['slug'])
        (copy,) = service.product.images.all()
        self.assertEqual(self._bytes(copy.image), self.photo)

    def test_an_uploaded_photo_is_kept_and_carries_no_credit(self):
        self._run()
        place = Place.objects.get(slug=data.PLACES[0]['slug'])
        mine = _jpeg((200, 40, 40))
        place.image.save('mine.jpg', ContentFile(mine), save=True)
        self.assertIsNone(place.photo_credit, 'the credit named a photo that is gone')

        self.download.reset_mock()
        self._run()
        place.refresh_from_db()
        self.assertEqual(self._bytes(place.image), mine)
        self.download.assert_not_called()

    def test_the_pages_name_the_author_and_link_the_licence(self):
        self._run()
        place_row, exp_row = data.PLACES[0], data.EXPERIENCES[0]
        for url, photo in (
            (f'/places/{place_row["slug"]}/', place_row['photo']),
            (f'/bookings/{exp_row["slug"]}/', exp_row['photo']),
        ):
            body = self.client.get(url).content.decode()
            self.assertIn('mx-photo-credit', body, url)
            self.assertIn(escape(photo['author']), body, url)
            self.assertIn(f'href="{escape(photo["source_url"])}"', body, url)


class HotelWithoutRoomsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from plugins.installed.catalog.models import Vendor

        host = Vendor.objects.create(name='Croatia Experience', slug='croatia-experience')
        cls.hotel = Property.objects.create(
            vendor=host,
            name='Hotel Esplanade Zagreb',
            slug='hotel-esplanade-zagreb',
            star_rating=5,
            region='zagreb',
            location='Zagreb',
            description='A hotel beside the main railway station.',
        )

    def setUp(self):
        _activate_theme(self, 'croatia')

    def test_the_card_asks_for_a_price_instead_of_showing_zero(self):
        body = self.client.get('/hotels/').content.decode()
        self.assertIn('hotel-esplanade-zagreb', body)
        self.assertNotRegex(body, r'0[.,]00')
        self.assertIn('Contact for price', body)

    def test_the_page_offers_an_enquiry_form(self):
        body = self.client.get('/hotels/hotel-esplanade-zagreb/').content.decode()
        self.assertIn('data-stay-enquiry', body)
        self.assertIn('Availability and prices', body)

    def test_an_enquiry_needs_no_room(self):
        response = self.client.post(
            '/hotels/hotel-esplanade-zagreb/book/',
            {'name': 'Ana', 'email': 'ana@example.com', 'adults': '2', 'message': 'June?'},
        )
        self.assertEqual(response.status_code, 302)
        enquiry = StayEnquiry.objects.get()
        self.assertEqual(enquiry.property, self.hotel)
        self.assertIsNone(enquiry.room_type)
        self.assertEqual(enquiry.message, 'June?')
        # The hotel page printed no messages, so the guest never saw the thanks.
        page = self.client.get(response['Location']).content.decode()
        self.assertIn('we&#x27;ll be in touch about availability', page)

    def test_an_enquiry_without_an_email_is_refused(self):
        self.client.post('/hotels/hotel-esplanade-zagreb/book/', {'name': 'Ana'})
        self.assertFalse(StayEnquiry.objects.exists())
