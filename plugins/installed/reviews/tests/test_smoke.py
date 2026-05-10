"""Reviews smoke test — write a review via the storefront endpoint and
assert it shows up filtered by is_approved + on the PDP context."""
from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from djmoney.money import Money


class ReviewsSmoke(TestCase):
    def setUp(self):
        from plugins.installed.catalog.models import Product
        self.product = Product.objects.create(
            name='Test Book', slug='test-book', sku='TST-1',
            status='active', price=Money(Decimal('10.00'), 'USD'),
        )
        self.user = get_user_model().objects.create_user(
            username='reader@example.com', email='reader@example.com',
            password='hunter2', first_name='Mara',
        )

    def test_post_creates_approved_review_visible_on_pdp(self):
        c = Client()
        c.force_login(self.user)
        resp = c.post(
            f'/reviews/add/{self.product.id}/',
            {'rating': '4', 'body': 'Took my breath away — quietly.'},
        )
        self.assertEqual(resp.status_code, 302)

        from plugins.installed.catalog.models import Review
        rows = Review.objects.filter(product=self.product, customer=self.user)
        self.assertEqual(rows.count(), 1)
        self.assertTrue(rows[0].is_approved)
        self.assertEqual(rows[0].rating, 4)

        from plugins.installed.storefront.views import _published_reviews
        rendered = _published_reviews(self.product.slug)
        self.assertEqual(len(rendered), 1)
        self.assertIn('★★★★☆', rendered[0]['stars'])
