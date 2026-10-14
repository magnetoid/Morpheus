"""The product editor carries a Booking details card for a listing's product (PRODUCT_FORM_CARDS)."""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.http import QueryDict
from django.test import TestCase
from djmoney.money import Money

from morpheus.core import MorpheusEvents, hook_registry
from plugins.installed.booking_marketplace.models import BookableService
from plugins.installed.booking_marketplace.products import ensure_product
from plugins.installed.catalog.models import Product, Vendor


class BookingDetailsCardTests(TestCase):
    def setUp(self):
        vendor = Vendor.objects.create(name='Makers', slug='makers', is_active=True)
        self.svc = BookableService.objects.create(
            vendor=vendor,
            name='Kayak the bay',
            slug='kayak-the-bay',
            listing_kind='experience',
            price=Money(Decimal('50'), 'EUR'),
            is_active=True,
            meeting_point='Kotor old town gate',
            highlights=['Caves'],
        )
        self.product = ensure_product(self.svc)
        self.admin = get_user_model().objects.create_superuser('boss@x.io', 'boss@x.io', 'pw')

    def _cards(self, product):
        cards = hook_registry.filter(MorpheusEvents.PRODUCT_FORM_CARDS, value=[], product=product)
        return [c for c in cards if c.get('template', '').startswith('booking_marketplace/')]

    def _save(self, **fields):
        post = QueryDict(mutable=True)
        for key, value in fields.items():
            post[f'booking__{key}'] = value
        hook_registry.fire(
            MorpheusEvents.PRODUCT_FORM_SAVED, product=self.product, post=post, files={}
        )
        self.svc.refresh_from_db()

    def test_the_editor_shows_the_card_for_a_listing_product(self):
        self.client.force_login(self.admin)
        html = self.client.get(f'/dashboard/products/{self.product.pk}/').content.decode()
        self.assertIn('name="booking__meeting_point"', html)
        self.assertIn('Kotor old town gate', html)

    def test_a_product_without_a_listing_gets_no_card(self):
        mug = Product.objects.create(
            name='Mug', slug='mug', sku='MUG', price=Money(Decimal('9'), 'EUR')
        )
        self.assertEqual(self._cards(mug), [])

    def test_saving_writes_the_booking_fields(self):
        self._save(
            duration_label='3 hours',
            highlights='A\nB\n',
            languages='English, Serbian',
            daily_capacity='12',
            meeting_point='Marina',
        )
        self.assertEqual(self.svc.duration_label, '3 hours')
        self.assertEqual(self.svc.highlights, ['A', 'B'])
        self.assertEqual(self.svc.languages, ['English', 'Serbian'])
        self.assertEqual((self.svc.daily_capacity, self.svc.meeting_point), (12, 'Marina'))

    def test_a_bad_number_keeps_the_stored_one(self):
        self._save(daily_capacity='lots', max_guests_per_booking='-3')
        self.assertEqual((self.svc.daily_capacity, self.svc.max_guests_per_booking), (10, 10))

    def test_a_save_without_the_card_changes_nothing(self):
        hook_registry.fire(
            MorpheusEvents.PRODUCT_FORM_SAVED,
            product=self.product,
            post=QueryDict(mutable=True),
            files={},
        )
        self.svc.refresh_from_db()
        self.assertEqual(
            (self.svc.highlights, self.svc.meeting_point), (['Caves'], 'Kotor old town gate')
        )

    def test_the_card_disappears_when_the_app_is_off(self):
        from plugins.registry import app_registry

        self.assertEqual(len(self._cards(self.product)), 1)
        app_registry._active.discard('booking_marketplace')
        self.addCleanup(app_registry._active.add, 'booking_marketplace')
        self.assertEqual(self._cards(self.product), [])

    def _save_rows(self, **lists):
        post = QueryDict(mutable=True)
        for key, values in lists.items():
            post.setlist(f'booking__{key}', values)
        hook_registry.fire(
            MorpheusEvents.PRODUCT_FORM_SAVED, product=self.product, post=post, files={}
        )
        self.svc.refresh_from_db()

    def test_saving_writes_the_itinerary_in_order(self):
        self._save_rows(
            itinerary_present=['1'],
            itinerary_title=['Meet at the gate', '', 'Paddle under the walls'],
            itinerary_detail=['Kit and a briefing.', 'a detail with no step', ''],
        )
        self.assertEqual(
            self.svc.itinerary,
            [
                {'title': 'Meet at the gate', 'detail': 'Kit and a briefing.'},
                {'title': 'Paddle under the walls', 'detail': ''},
            ],
        )

    def test_saving_keeps_only_answered_questions(self):
        self._save_rows(
            faqs_present=['1'],
            faqs_q=['Do I need to swim?', 'Can children come?', ''],
            faqs_a=['A little.', '', 'an answer with no question'],
        )
        self.assertEqual(self.svc.faqs, [{'q': 'Do I need to swim?', 'a': 'A little.'}])

    def test_a_save_without_the_rows_keeps_them(self):
        self.svc.itinerary = [{'title': 'Meet', 'detail': ''}]
        self.svc.faqs = [{'q': 'Swim?', 'a': 'Yes.'}]
        self.svc.save()
        self._save(meeting_point='Kotor Sea Gate')
        self.assertEqual(self.svc.itinerary, [{'title': 'Meet', 'detail': ''}])
        self.assertEqual(self.svc.faqs, [{'q': 'Swim?', 'a': 'Yes.'}])

    def test_the_card_shows_the_rows_and_spares(self):
        self.svc.faqs = [{'q': 'Do I need to swim?', 'a': 'A little.'}]
        self.svc.save()
        self.client.force_login(self.admin)
        html = self.client.get(f'/dashboard/products/{self.product.pk}/').content.decode()
        self.assertIn('value="Do I need to swim?"', html)
        self.assertEqual(html.count('name="booking__faqs_q"'), 4)
        self.assertEqual(html.count('name="booking__itinerary_title"'), 4)
