"""Montenegro's storefront shows only what the store can back, and nothing covers it.

The audit (2026-10-13) found "Loved by 10,000+ Customers", "4.9 average rating" and
"500+ experiences" on the home page, "Guest favourite" and a "4.9 (415)" rating on
every card from 559 seeded reviews with no booking behind any of them, and a
category strip pinned under the header that covered 40% of the screen.
"""

from __future__ import annotations

import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from djmoney.money import Money

from plugins.installed.booking_marketplace import services as S
from plugins.installed.booking_marketplace.models import BookableService, Booking, ServiceReview
from themes.test_head_contract import _activate_theme


class MontenegroClaimTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from plugins.installed.catalog.models import Vendor

        vendor = Vendor.objects.create(name='Tara Sport', slug='tara-sport', is_active=True)
        cls.svc = BookableService.objects.create(
            vendor=vendor,
            name='Tara Canyon Rafting',
            slug='tara-canyon-rafting',
            listing_kind='experience',
            price=Money(Decimal('70'), 'EUR'),
            rating=Decimal('4.9'),
            review_count=415,
            is_bestseller=True,
            is_active=True,
        )
        ServiceReview.objects.bulk_create(
            ServiceReview(service=cls.svc, author_name='Seeded', rating=5, body='Seeded text.')
            for _ in range(3)
        )

    def setUp(self):
        _activate_theme(self, 'montenegro')

    def _verified_review(self, rating, email):
        U = get_user_model()
        guest = U.objects.create(**{U.USERNAME_FIELD: email})
        Booking.objects.create(
            service=self.svc,
            customer=guest,
            customer_name='Guest',
            customer_email=email,
            booking_date=timezone.localdate() + datetime.timedelta(days=2),
            guests=1,
            status='confirmed',
        )
        S.create_review(self.svc, user=guest, rating=rating, body='A real trip down the canyon.')

    def _home(self):
        resp = self.client.get('/')
        self.assertEqual(resp.status_code, 200)
        return resp.content.decode()

    def test_the_home_page_claims_no_totals_it_cannot_back(self):
        html = self._home()
        for claim in ('10,000+', '4.9 average rating', '500+ experiences', 'Guest favourite'):
            self.assertNotIn(claim, html)

    def test_the_category_strip_does_not_cover_the_page(self):
        html = self._home()
        self.assertNotIn('sticky top-[72px]', html)
        self.assertIn('montenegro/refresh.css', html)

    def test_seeded_reviews_show_no_rating_and_no_quotes(self):
        html = self._home()
        self.assertNotIn('(415)', html)
        self.assertNotIn('Seeded text.', html)
        self.assertIn('Top pick', html)

    def test_verified_reviews_show_their_own_rating_and_quote(self):
        self._verified_review(4, 'a@example.com')
        self._verified_review(5, 'b@example.com')
        html = self._home()
        self.assertIn('4.5', html)
        self.assertIn('(2)', html)
        self.assertIn('A real trip down the canyon.', html)
        self.assertNotIn('Seeded text.', html)

    def test_the_listing_page_reads_verified_reviews_only(self):
        html = self.client.get(f'/bookings/{self.svc.slug}/').content.decode()
        self.assertNotIn('415', html)
        self.assertNotIn('Superhost', html)

    def test_no_footer_link_goes_nowhere(self):
        self.assertNotIn('href="#" class="hover:text-muted-foreground', self._home())
