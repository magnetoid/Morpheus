"""seed_reviews — coverage, idempotency, denormalised sync."""

from django.core.management import call_command
from django.test import TestCase
from djmoney.money import Money

from plugins.installed.booking_marketplace.models import BookableService, ServiceReview
from plugins.installed.catalog.models import Category, Vendor


class SeedReviewsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        v = Vendor.objects.create(name='H', slug='h', is_active=True)
        c = Category.objects.create(name='Adventure', slug='adventure')
        for i in range(3):
            BookableService.objects.create(
                vendor=v,
                category=c,
                name=f'e{i}',
                slug=f'e{i}',
                price=Money(40, 'EUR'),
                listing_kind='experience',
                is_active=True,
            )

    def test_every_experience_reviewed_and_synced(self):
        call_command('seed_reviews', verbosity=0)
        for svc in BookableService.objects.filter(listing_kind='experience'):
            n = svc.reviews.count()
            self.assertGreaterEqual(n, 3)
            self.assertLessEqual(n, 8)
            svc.refresh_from_db()
            self.assertEqual(svc.review_count, n)
            self.assertGreater(float(svc.rating), 3.0)

    def test_idempotent(self):
        call_command('seed_reviews', verbosity=0)
        n1 = ServiceReview.objects.count()
        call_command('seed_reviews', verbosity=0)
        self.assertEqual(ServiceReview.objects.count(), n1)
