"""An experience's details and categories read in the page's language (v0.191.0).

The Codex report on Montenegro (2026-11) found /sr/ experience pages with a
Serbian name and an English body: the duration, meeting point, cancellation
policy, highlights, itinerary and guest questions are the listing's own text and
nothing could translate them; the category chips said "Adventure"; dates in the
booking form said "Nov.". The details are registered as "Experience details",
whose page exists in a language only when they and the Product's text are both
translated there.
"""

from __future__ import annotations

import datetime

from django.core.cache import cache
from django.template import Context, Template
from django.test import Client, TestCase, override_settings
from django.utils import translation
from djmoney.money import Money

from core.i18n.services import (
    content_languages,
    overlay_translation,
    set_translation,
    source_values,
    spec_for,
)
from plugins.installed.booking_marketplace.models import BookableService
from plugins.installed.booking_marketplace.tests._theme import MontenegroThemeMixin
from plugins.installed.booking_marketplace.tests.test_translated_pages import (
    BILINGUAL,
    _translate,
    _vendor,
)

SERBIAN_DETAILS = {
    'duration_label': '4 sata',
    'meeting_point': 'Mol u Kotoru',
    'cancellation_policy': 'Besplatno otkazivanje do 24 sata ranije.',
    'highlights': 'Pećina\nIzlazak sunca',
    'included': 'Vodič\nKajak',
    'not_included': 'Ručak',
    'what_to_bring': 'Kupaći kostim',
    'itinerary': 'Sastanak\nNa molu.\n\nVeslanje\nPreko zaliva.',
    'faqs': 'Da li treba iskustvo?\nNe, vodič vas uči.',
}


@override_settings(**BILINGUAL)
class ExperienceDetailsTests(MontenegroThemeMixin, TestCase):
    def setUp(self):
        cache.clear()

    def _service(self):
        from plugins.installed.booking_marketplace.products import ensure_product

        service = BookableService.objects.create(
            vendor=_vendor(),
            name='Bay Kayak Tour',
            slug='bay-kayak-tour',
            short_description='Paddle the bay at dawn.',
            description='Paddle the bay at dawn with a local guide.',
            price=Money(50, 'EUR'),
            listing_kind='experience',
            duration_label='4 hours',
            meeting_point='Kotor pier',
            cancellation_policy='Free cancellation up to 24 hours before.',
            highlights=['The cave', 'Sunrise'],
            included=['Guide', 'Kayak'],
            not_included=['Lunch'],
            what_to_bring=['Swimwear'],
            itinerary=[
                {'time': '06:00', 'title': 'Meet', 'detail': 'At the pier.'},
                {'time': '06:30', 'title': 'Paddle', 'detail': 'Across the bay.'},
            ],
            faqs=[{'q': 'Do I need experience?', 'a': 'No, the guide teaches you.'}],
            is_active=True,
        )
        _translate(ensure_product(service), 'Kajakom kroz zaliv')
        return service

    def _translate_details(self, service):
        for field, value in SERBIAN_DETAILS.items():
            set_translation(service, field, 'sr', value)

    def _get(self, path):
        cache.clear()
        response = Client().get(path)
        self.assertEqual(response.status_code, 200, path)
        body = response.content.decode('utf-8')
        return body.split('</head>', 1)[0], body

    def test_the_details_are_registered_as_text_a_translator_edits(self):
        service = self._service()
        values = source_values(service, spec_for(service))
        self.assertEqual(values['highlights'], 'The cave\nSunrise')
        self.assertEqual(values['itinerary'], 'Meet\nAt the pier.\n\nPaddle\nAcross the bay.')
        self.assertEqual(values['faqs'], 'Do I need experience?\nNo, the guide teaches you.')

    def test_the_page_shows_the_translated_details(self):
        service = self._service()
        self._translate_details(service)
        head, body = self._get('/sr/bookings/bay-kayak-tour/')
        for text in ('Mol u Kotoru', 'Sastanak', 'Preko zaliva.', 'Da li treba iskustvo?', 'Vodič'):
            self.assertIn(text, body)
        self.assertNotIn('Do I need experience?', body)
        self.assertIn('rel="canonical" href="http://testserver/sr/bookings/bay-kayak-tour/"', head)
        self.assertIn('hreflang="sr"', head)
        # The graph's guest questions and itinerary are the page's.
        self.assertIn('"name":"Da li treba iskustvo?"', head)
        self.assertIn('"name":"Sastanak"', head)
        _, english = self._get('/bookings/bay-kayak-tour/')
        self.assertIn('Do I need experience?', english)
        self.assertNotIn('Da li treba iskustvo?', english)

    def test_untranslated_details_keep_the_page_english_for_search(self):
        self._service()
        head, body = self._get('/sr/bookings/bay-kayak-tour/')
        self.assertIn('Do I need experience?', body)
        self.assertIn('rel="canonical" href="http://testserver/bookings/bay-kayak-tour/"', head)
        self.assertNotIn('hreflang=', head)

    def test_details_without_the_product_are_not_a_serbian_page(self):
        from plugins.installed.booking_marketplace.products import ensure_product

        service = BookableService.objects.create(
            vendor=_vendor(),
            name='Old Town Walk',
            slug='old-town-walk',
            short_description='Walk the walls.',
            price=Money(20, 'EUR'),
            duration_label='2 hours',
            is_active=True,
        )
        ensure_product(service)
        for field, value in source_values(service, spec_for(service)).items():
            if value.strip():
                set_translation(service, field, 'sr', f'Srpski {field}')
        self.assertEqual(content_languages(service), {'en'})
        _translate(service.product, 'Šetnja starim gradom')
        service.refresh_from_db()
        self.assertEqual(content_languages(service), {'en', 'sr'})

    def test_a_save_after_the_overlay_keeps_the_english_lists(self):
        service = self._service()
        self._translate_details(service)
        overlay_translation([service], 'sr')
        self.assertEqual(service.faqs, [{'q': 'Da li treba iskustvo?', 'a': 'Ne, vodič vas uči.'}])
        self.assertEqual(service.itinerary[0]['time'], '06:00')
        service.save()
        service.refresh_from_db()
        self.assertEqual(
            service.faqs, [{'q': 'Do I need experience?', 'a': 'No, the guide teaches you.'}]
        )
        self.assertEqual(service.highlights, ['The cave', 'Sunrise'])


@override_settings(**BILINGUAL)
class CategoryNameTests(MontenegroThemeMixin, TestCase):
    def setUp(self):
        cache.clear()

    def test_a_listing_category_is_named_in_the_page_language(self):
        from plugins.installed.booking_marketplace.products import ensure_product
        from plugins.installed.catalog.models import Category

        category = Category.objects.create(name='Adventure', slug='adventure', is_active=True)
        set_translation(category, 'name', 'sr', 'Avantura')
        service = BookableService.objects.create(
            vendor=_vendor(),
            name='Canyon Jump',
            slug='canyon-jump',
            short_description='Jump into the canyon.',
            price=Money(70, 'EUR'),
            category=category,
            is_active=True,
        )
        ensure_product(service)
        cache.clear()
        body = Client().get('/sr/bookings/').content.decode('utf-8')
        self.assertIn('Avantura', body)
        cache.clear()
        english = Client().get('/bookings/').content.decode('utf-8')
        self.assertIn('Adventure', english)
        self.assertNotIn('Avantura', english)


class BookingDayTests(TestCase):
    def _render(self, language, arg=''):
        template = Template(
            '{% load booking_tags %}{{ day|booking_day' + (f':"{arg}"' if arg else '') + ' }}'
        )
        with translation.override(language):
            return template.render(Context({'day': datetime.date(2026, 11, 28)}))

    def test_serbian_dates_are_latin_and_serbian(self):
        self.assertIn('nov', self._render('sr').lower())
        self.assertNotIn('Nov.', self._render('sr'))
        self.assertIn('2026', self._render('sr'))
        self.assertNotIn('2026', self._render('sr', 'no year'))

    def test_english_dates(self):
        self.assertIn('Nov', self._render('en'))


@override_settings(**BILINGUAL)
class GiftBannerTests(MontenegroThemeMixin, TestCase):
    def _home(self):
        cache.clear()
        return Client().get('/').content.decode('utf-8')

    def test_no_banner_without_a_gift_card_for_sale(self):
        self.assertNotIn('Buy Gift Card', self._home())

    def test_the_banner_links_the_gift_card(self):
        from plugins.installed.catalog.models import Product

        Product.objects.create(
            name='Gift card',
            slug='gift-card',
            sku='GIFT-CARD',
            price=Money(25, 'EUR'),
            status='active',
        )
        body = self._home()
        self.assertIn('Buy Gift Card', body)
        self.assertIn('href="/products/gift-card/"', body)
        self.assertNotIn('€500', body)


@override_settings(**BILINGUAL)
class DetailsEditorTests(TestCase):
    def test_a_list_field_is_edited_as_text_and_shown_as_a_list(self):
        from django.contrib.auth import get_user_model

        from plugins.installed.booking_marketplace.products import ensure_product

        service = BookableService.objects.create(
            vendor=_vendor(),
            name='Bay Kayak Tour',
            slug='bay-kayak-tour',
            price=Money(50, 'EUR'),
            faqs=[{'q': 'Do I need experience?', 'a': 'No.'}],
            is_active=True,
        )
        ensure_product(service)
        staff = get_user_model().objects.create_user('o', 'o@example.test', 'x', is_staff=True)
        client = Client()
        client.force_login(staff)
        url = f'/dashboard/apps/localization/translations/booking_marketplace.experience/{service.pk}/sr/'
        page = client.get(url).content.decode()
        self.assertIn('Do I need experience?\nNo.', page)
        response = client.post(
            url,
            {
                'action': 'save',
                'f-faqs': 'Treba li iskustvo?\r\nNe.\r\n\r\nKoliko traje?\r\nDva sata.',
                'f-cancellation_policy': 'Besplatno otkazivanje.',
            },
        )
        self.assertEqual(response.status_code, 302)
        overlay_translation([service], 'sr')
        self.assertEqual(
            service.faqs,
            [{'q': 'Treba li iskustvo?', 'a': 'Ne.'}, {'q': 'Koliko traje?', 'a': 'Dva sata.'}],
        )
