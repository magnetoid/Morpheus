"""The experience page answers first and lays out the facts a traveller decides on."""

from __future__ import annotations

import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from djmoney.money import Money

from plugins.installed.booking_marketplace import services as S
from plugins.installed.booking_marketplace.models import BookableService, Booking, ServiceReview
from plugins.installed.booking_marketplace.products import ensure_product
from plugins.installed.booking_marketplace.tests._theme import MontenegroThemeMixin
from plugins.installed.catalog.models import Vendor

SUMMARY = 'Two calm hours paddling under the walls of Kotor at dawn, for beginners.'


class ExperiencePageStructureTests(MontenegroThemeMixin, TestCase):
    def setUp(self):
        vendor = Vendor.objects.create(name='Makers', slug='makers', is_active=True)
        self.svc = BookableService.objects.create(
            vendor=vendor,
            name='Kayak the bay',
            slug='kayak-the-bay',
            listing_kind='experience',
            region='kotor',
            location='Kotor',
            price=Money(Decimal('50'), 'EUR'),
            is_active=True,
            short_description=SUMMARY,
            description='Paddle the bay.',
            duration_label='2 hours',
            max_guests_per_booking=8,
            languages=['English', 'Montenegrin'],
            meeting_point='Kotor Sea Gate, by the ticket kiosk',
            cancellation_policy='Free cancellation up to 24 hours before.',
            faqs=[{'q': 'Do I need to swim?', 'a': 'A little; you wear a vest.'}],
        )
        self.product = ensure_product(self.svc)

    def _page(self):
        resp = self.client.get(f'/bookings/{self.svc.slug}/')
        self.assertEqual(resp.status_code, 200)
        return resp.content.decode()

    def _section(self, html, marker):
        start = html.index(marker)
        return html[start : html.index('</section>', start)]

    def test_the_summary_answers_first_under_the_title(self):
        html = self._page()
        self.assertLess(html.index('<h1'), html.index('id="experience-summary"'))
        self.assertLess(html.index('id="experience-summary"'), html.index('id="at-a-glance"'))
        start = html.index('id="experience-summary"')
        self.assertIn(SUMMARY, html[start : start + 600])

    def test_at_a_glance_lists_the_known_facts(self):
        block = self._section(self._page(), 'id="at-a-glance"')
        for marker, fact in (
            ('glance-duration', '2 hours'),
            ('glance-group', '8'),
            ('glance-languages', 'English, Montenegrin'),
            ('glance-meeting-point', 'Kotor Sea Gate, by the ticket kiosk'),
            ('glance-cancellation', 'Free cancellation up to 24 hours before.'),
        ):
            with self.subTest(marker=marker):
                self.assertIn(f'id="{marker}"', block)
                self.assertIn(fact, block)

    def test_at_a_glance_leaves_out_what_the_listing_does_not_know(self):
        BookableService.objects.filter(pk=self.svc.pk).update(languages=[], meeting_point='')
        block = self._section(self._page(), 'id="at-a-glance"')
        self.assertNotIn('id="glance-languages"', block)
        self.assertNotIn('id="glance-meeting-point"', block)
        self.assertIn('id="glance-duration"', block)

    def test_the_meeting_point_shows_where_youll_be(self):
        html = self._page()
        self.assertIn(
            'Kotor Sea Gate, by the ticket kiosk', self._section(html, 'id="meeting-point"')
        )

    def test_the_description_has_its_heading(self):
        self.assertIn('id="about"', self._page())

    def test_guest_questions_come_before_the_reviews(self):
        html = self._page()
        self.assertEqual(html.count('id="guest-questions"'), 1)
        self.assertEqual(html.count('id="reviews"'), 1)
        self.assertLess(html.index('id="guest-questions"'), html.index('id="reviews"'))

    def test_a_product_listing_has_no_at_a_glance(self):
        BookableService.objects.filter(pk=self.svc.pk).update(listing_kind='product')
        self.assertNotIn('id="at-a-glance"', self._page())

    def test_an_unlinked_listing_still_renders(self):
        BookableService.objects.filter(pk=self.svc.pk).update(product=None)
        html = self._page()
        self.assertIn(SUMMARY, html)
        self.assertIn('id="at-a-glance"', html)

    def test_the_reviews_heading_rates_only_verified_reviews(self):
        ServiceReview.objects.create(service=self.svc, rating=5, author_name='Seed', body='Seeded.')
        self.assertNotIn('id="reviews-rating"', self._page())
        U = get_user_model()
        guest = U.objects.create(**{U.USERNAME_FIELD: 'guest@x.io'})
        Booking.objects.create(
            service=self.svc,
            customer=guest,
            customer_name='Guest',
            customer_email='guest@x.io',
            booking_date=timezone.localdate() + datetime.timedelta(days=2),
            guests=1,
            status='confirmed',
        )
        S.create_review(self.svc, user=guest, rating=4, body='A real morning on the water.')
        self.assertIn('id="reviews-rating"', self._page())
