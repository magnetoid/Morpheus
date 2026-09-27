"""Re-submitting a review must not undo the merchant's moderation.

Hiding a review means leaving it unapproved (`is_approved=False`) — that is what
the dashboard's "Hide" action writes and what `reviews.delete` recommends
instead of deleting. The storefront endpoint saved every submission with
`update_or_create(..., defaults={'is_approved': True})`, so the author of a
hidden review only had to post the form again (any text) to put it back on the
product page and into the rating aggregate.
"""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from djmoney.money import Money


class ResubmitKeepsModerationTests(TestCase):
    def setUp(self):
        from plugins.installed.catalog.models import Product

        self.product = Product.objects.create(
            name='Moderated Book',
            slug='moderated-book',
            sku='MOD-1',
            status='active',
            price=Money(Decimal('10.00'), 'USD'),
        )
        self.user = get_user_model().objects.create_user(
            username='critic@example.com', email='critic@example.com', password='pw-12345!'
        )
        self.client.force_login(self.user)
        self.url = f'/reviews/add/{self.product.id}/'

    def test_a_hidden_review_stays_hidden_when_its_author_posts_again(self):
        from plugins.installed.catalog.models import Review

        self.client.post(self.url, {'rating': '1', 'body': 'abusive text'})
        review = Review.objects.get(product=self.product, customer=self.user)
        review.is_approved = False  # the dashboard "Hide" action
        review.save(update_fields=['is_approved', 'updated_at'])

        self.client.post(self.url, {'rating': '1', 'body': 'same text, posted again'})

        review.refresh_from_db()
        self.assertFalse(review.is_approved, 'resubmitting un-hid a moderated review')
        self.assertEqual(review.body, 'same text, posted again')

    def test_a_first_review_is_still_published(self):
        from plugins.installed.catalog.models import Review

        self.client.post(self.url, {'rating': '5', 'body': 'lovely'})
        self.assertTrue(Review.objects.get(product=self.product, customer=self.user).is_approved)
