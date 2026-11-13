"""The travel store's pages show a reviewed translation on /sr/ (v0.160.0).

Until v0.160.0 nothing on the storefront read the translations the platform could
store: every experience, place, hotel and event was English under /sr/. A page now
shows an object's reviewed translation once every field it fills is translated
(core.i18n), and the English page stays as it was.
"""

from __future__ import annotations

from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from djmoney.money import Money

from core.i18n.services import set_translation, source_values, spec_for
from plugins.installed.booking_marketplace.models import BookableService, Event, Place, Property
from plugins.installed.booking_marketplace.tests._theme import MontenegroThemeMixin

BILINGUAL = {
    'LANGUAGES': [('en', 'English'), ('sr', 'Srpski')],
    'LANGUAGE_CODE': 'en',
    'BOOKING_LISTING_MODE': False,
}


def _translate(obj, name: str) -> None:
    """A reviewed Serbian translation of every field the object fills."""
    for field, value in source_values(obj, spec_for(obj)).items():
        if value.strip():
            text = name if field == 'name' else f'Srpski tekst {field}'
            set_translation(obj, field, 'sr', text)


def _vendor():
    from plugins.installed.catalog.models import Vendor

    return Vendor.objects.create(name='Hosts', slug='hosts', is_active=True)


@override_settings(**BILINGUAL)
class TranslatedPagesTests(MontenegroThemeMixin, TestCase):
    def setUp(self):
        cache.clear()

    def _body(self, path: str) -> str:
        cache.clear()
        response = Client().get(path)
        self.assertEqual(response.status_code, 200, path)
        return response.content.decode('utf-8')

    def _experience(self):
        from plugins.installed.booking_marketplace.products import ensure_product

        service = BookableService.objects.create(
            vendor=_vendor(),
            name='Bay Kayak Tour',
            slug='bay-kayak-tour',
            short_description='Paddle the bay at dawn.',
            description='Paddle the bay at dawn with a local guide.',
            price=Money(50, 'EUR'),
            listing_kind='experience',
            is_active=True,
        )
        _translate(ensure_product(service), 'Kajakom kroz zaliv')
        return service

    def test_an_experience_page_and_the_list(self):
        self._experience()
        for path in ('/sr/bookings/bay-kayak-tour/', '/sr/bookings/'):
            body = self._body(path)
            self.assertIn('Kajakom kroz zaliv', body, path)
        for path in ('/bookings/bay-kayak-tour/', '/bookings/'):
            body = self._body(path)
            self.assertIn('Bay Kayak Tour', body, path)
            self.assertNotIn('Kajakom kroz zaliv', body, path)

    def test_an_experience_saved_after_the_page_keeps_its_english(self):
        service = self._experience()
        self._body('/sr/bookings/bay-kayak-tour/')
        service.refresh_from_db()
        service.product.refresh_from_db()
        self.assertEqual(service.name, 'Bay Kayak Tour')
        self.assertEqual(service.product.name, 'Bay Kayak Tour')

    def test_a_place_page(self):
        place = Place.objects.create(
            name='Perast Old Town',
            slug='perast-old-town',
            summary='A baroque town on the bay.',
            description='Churches and palaces by the water.',
            is_active=True,
        )
        _translate(place, 'Stari grad Perast')
        self.assertIn('Stari grad Perast', self._body('/sr/places/perast-old-town/'))
        english = self._body('/places/perast-old-town/')
        self.assertIn('Perast Old Town', english)
        self.assertNotIn('Stari grad Perast', english)

    def test_a_stay_page(self):
        prop = Property.objects.create(
            vendor=_vendor(),
            name='Villa Bayview',
            slug='villa-bayview',
            short_description='Rooms over the water.',
            description='A stone villa on the shore.',
            location='Perast',
            is_active=True,
        )
        _translate(prop, 'Vila sa pogledom na zaliv')
        self.assertIn('Vila sa pogledom na zaliv', self._body('/sr/hotels/villa-bayview/'))
        english = self._body('/hotels/villa-bayview/')
        self.assertIn('Villa Bayview', english)
        self.assertNotIn('Vila sa pogledom na zaliv', english)

    def test_an_event_page(self):
        event = Event.objects.create(
            name='Summer Jazz Night',
            slug='summer-jazz-night',
            summary='Jazz under the walls.',
            month=7,
            is_active=True,
        )
        _translate(event, 'Letnje džez veče')
        self.assertIn('Letnje džez veče', self._body('/sr/events/summer-jazz-night/'))
        english = self._body('/events/summer-jazz-night/')
        self.assertIn('Summer Jazz Night', english)
        self.assertNotIn('Letnje džez veče', english)

    def test_an_untranslated_place_names_the_english_page(self):
        Place.objects.create(name='Lovćen', slug='lovcen', summary='A mountain.', is_active=True)
        body = self._body('/sr/places/lovcen/')
        head = body.split('</head>', 1)[0]
        self.assertIn('rel="canonical" href="http://testserver/places/lovcen/"', head)
        self.assertNotIn('hreflang=', head)
