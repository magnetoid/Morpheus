"""A restock must reach the shoppers who asked to hear about it.

Every theme's product page posts "email me when it's back" to
`back_in_stock_subscribe`, which stores a `BackInStockSubscription` and flashes
"We'll email you when this title is back." The email task,
`inventory.notify_back_in_stock`, existed — but nothing ever enqueued it, so no
subscriber was ever told, however much stock came back in.
"""

from __future__ import annotations

from django.core import mail
from django.test import TestCase

from plugins.installed.catalog.models import Product, ProductVariant
from plugins.installed.inventory.models import (
    BackInStockSubscription,
    StockLevel,
    StockMovement,
    Warehouse,
)


class BackInStockNotifyTests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(
            name='Sold-out Atlas', slug='sold-out-atlas', sku='ATLAS-1', status='active', price=10
        )
        variant = ProductVariant.objects.create(product=self.product, name='Std', sku='ATLAS-V1')
        wh = Warehouse.objects.create(name='Main', code='MAIN', is_default=True)
        self.level = StockLevel.objects.create(variant=variant, warehouse=wh, quantity=0)
        self.sub = BackInStockSubscription.objects.create(
            product=self.product, email='fan@example.com'
        )

    def test_restocking_emails_the_waiting_subscriber_once(self):
        with self.captureOnCommitCallbacks(execute=True):
            StockMovement.record(self.level, 'receive', 5, reference='PO-7')

        self.assertEqual([m.to for m in mail.outbox], [['fan@example.com']])
        self.assertIn('Sold-out Atlas', mail.outbox[0].subject)
        self.sub.refresh_from_db()
        self.assertIsNotNone(self.sub.notified_at)

        # Further stock movements do not re-mail someone already told.
        with self.captureOnCommitCallbacks(execute=True):
            StockMovement.record(self.level, 'receive', 3, reference='PO-8')
        self.assertEqual(len(mail.outbox), 1)

    def test_a_save_that_leaves_it_sold_out_sends_nothing(self):
        with self.captureOnCommitCallbacks(execute=True):
            StockMovement.record(self.level, 'adjustment', 0, reference='count')
        self.assertEqual(mail.outbox, [])
        self.sub.refresh_from_db()
        self.assertIsNone(self.sub.notified_at)
