"""The travel store marks a translation an AI drafted where it shows one (v0.177.0).

An experience shows its catalog Product's translation, so its page carries the
Product's marks under the description; a place, a hotel or an event carries them
at the end of the page. A person's translation carries none (EU AI Act Art. 50).
"""

from __future__ import annotations

from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from djmoney.money import Money

from core.i18n.services import set_translation, source_values, spec_for
from plugins.installed.ai_content.seo_graph import GENERATED
from plugins.installed.booking_marketplace.models import BookableService, Place
from plugins.installed.booking_marketplace.tests._theme import MontenegroThemeMixin
from plugins.installed.booking_marketplace.tests.test_translated_pages import BILINGUAL, _vendor


def _translate(obj, name: str, *, machine: bool) -> list[str]:
    """A reviewed Serbian translation of every field the object fills; the fields."""
    fields = []
    for field, value in source_values(obj, spec_for(obj)).items():
        if value.strip():
            text = name if field == 'name' else f'Srpski tekst {field}'
            set_translation(obj, field, 'sr', text, machine_translated=machine)
            fields.append(field)
    return fields


@override_settings(**BILINGUAL)
class TranslationMarkTests(MontenegroThemeMixin, TestCase):
    def setUp(self):
        cache.clear()

    def _body(self, path: str) -> str:
        cache.clear()
        response = Client().get(path)
        self.assertEqual(response.status_code, 200, path)
        return response.content.decode('utf-8')

    def _experience(self, *, machine: bool):
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
        return _translate(ensure_product(service), 'Kajakom kroz zaliv', machine=machine)

    def _place(self, *, machine: bool):
        place = Place.objects.create(
            name='Perast Old Town',
            slug='perast-old-town',
            summary='A baroque town on the bay.',
            description='Churches and palaces by the water.',
            is_active=True,
        )
        return _translate(place, 'Stari grad Perast', machine=machine)

    def test_an_ai_translated_experience_is_marked(self):
        fields = self._experience(machine=True)
        body = self._body('/sr/bookings/bay-kayak-tour/')
        self.assertIn('Kajakom kroz zaliv', body)
        self.assertIn(f'data-ai-generated="{" ".join(fields)}"', body)

    def test_an_ai_translated_place_is_marked(self):
        fields = self._place(machine=True)
        body = self._body('/sr/places/perast-old-town/')
        self.assertIn('Stari grad Perast', body)
        self.assertIn(f'data-ai-generated="{" ".join(fields)}"', body)
        self.assertIn(GENERATED, body)

    def test_a_persons_translation_and_the_english_pages_are_not_marked(self):
        self._experience(machine=False)
        self._place(machine=False)
        for path in (
            '/sr/bookings/bay-kayak-tour/',
            '/sr/places/perast-old-town/',
            '/bookings/bay-kayak-tour/',
            '/places/perast-old-town/',
        ):
            body = self._body(path)
            self.assertNotIn('data-ai-generated', body, path)
            self.assertNotIn(GENERATED, body, path)
