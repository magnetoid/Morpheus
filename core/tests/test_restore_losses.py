"""What restoring a backup loses, as each app counts it (safe deploys, part 4)."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from djmoney.money import Money

from core import restore
from plugins.installed.catalog.models import Product


class RestoreLossesTests(TestCase):
    def test_customers_and_products_since_the_backup_are_counted(self):
        since = timezone.now()
        User = get_user_model()
        early = User.objects.create_user(username='early', email='e@x.io', password='pw')
        User.objects.filter(pk=early.pk).update(date_joined=since - timedelta(hours=1))
        User.objects.create_user(username='late', email='l@x.io', password='pw')
        User.objects.create_user(username='crew', email='c@x.io', password='pw', is_staff=True)
        Product.objects.create(
            name='Radio',
            slug='radio-r3',
            sku='R3-1',
            price=Money(Decimal('29.00'), 'USD'),
            status='active',
        )
        rows = {row['label']: row['count'] for row in restore.losses(since)}
        self.assertEqual(rows['customers signed up'], 1)
        self.assertEqual(rows['products added or changed'], 1)

    def test_nothing_changed_nothing_listed(self):
        self.assertEqual(restore.losses(timezone.now() + timedelta(days=1)), [])
