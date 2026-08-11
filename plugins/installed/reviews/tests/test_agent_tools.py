"""Review-moderation agent commands — Linda triages the review queue."""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from djmoney.money import Money

from plugins.installed.catalog.models import Product, Review
from plugins.installed.reviews.agent_tools import (
    reviews_approve_tool,
    reviews_delete_tool,
    reviews_list_pending_tool,
)
from plugins.installed.reviews.app import ReviewsPlugin


class ReviewModerationToolTests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(
            name='A Book',
            slug='a-book',
            sku='BK-1',
            status='active',
            price=Money(Decimal('20.00'), 'USD'),
            short_description='s',
            description='d',
            product_type='simple',
        )
        self.cust = get_user_model().objects.create_user(
            username='r', email='r@example.test', password='pw'
        )
        self.review = Review.objects.create(
            product=self.product, customer=self.cust, rating=5, body='Great!', is_approved=False
        )

    def test_plugin_contributes_three_tools(self):
        names = {t.name for t in ReviewsPlugin().contribute_agent_tools()}
        self.assertEqual(names, {'reviews.list_pending', 'reviews.approve', 'reviews.delete'})

    def test_list_pending_finds_unapproved(self):
        out = reviews_list_pending_tool.invoke({}).output
        self.assertEqual(out['count'], 1)
        self.assertFalse(out['pending'][0]['is_approved'])

    def test_approve_flips_flag_and_clears_queue(self):
        out = reviews_approve_tool.invoke({'review_id': str(self.review.id)}).output
        self.assertTrue(out['is_approved'])
        self.review.refresh_from_db()
        self.assertTrue(self.review.is_approved)
        self.assertEqual(reviews_list_pending_tool.invoke({}).output['count'], 0)

    def test_delete_removes_review(self):
        out = reviews_delete_tool.invoke({'review_id': str(self.review.id)}).output
        self.assertTrue(out['deleted'])
        self.assertFalse(Review.objects.filter(id=self.review.id).exists())

    def test_unknown_id_errors(self):
        import uuid

        out = reviews_approve_tool.invoke({'review_id': str(uuid.uuid4())}).output
        self.assertIn('error', out)

    def test_scopes(self):
        self.assertEqual(reviews_list_pending_tool.scopes, ['catalog.read'])
        self.assertEqual(reviews_approve_tool.scopes, ['catalog.write'])
