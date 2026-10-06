"""DSers' tracking export comes back and ships the orders the platform way.

The file DSers lets a merchant download after ordering carries the store's
order number, the AliExpress order number and the tracking number; the exact
header spelling is only visible to an account holder, so the importer matches
headers tolerantly. Shipping goes through ``Order.ship()`` and an
``orders.Fulfillment`` row — the owners of that state — so the "on its way"
email, the post-purchase follow-ups and the merchant webhooks fire exactly as
they do for a hand-fulfilled order.
"""

from __future__ import annotations

from django.test import TestCase

from morpheus.core import MorpheusEvents, hook_registry
from plugins.installed.dsers.tests._fixtures import paid_order, physical_product

CSV = (
    'Order number,AliExpress order number,Tracking number,Carrier\n'
    '{number},8172635401234567,LP123456789CN,AliExpress Standard Shipping\n'
)


class TrackingImportTests(TestCase):
    def setUp(self):
        from plugins.installed.dsers.models import OrderSync
        from plugins.registry import app_registry

        self.plugin = app_registry.get('dsers')
        self.plugin.set_config('tracking_url_template', 'https://t.17track.net/en#nums={tracking}')
        self.addCleanup(self.plugin.invalidate_config_cache)
        self.product, self.variant = physical_product()
        self.order = paid_order([(self.product, self.variant, 2)], status='processing')
        OrderSync.objects.create(order=self.order, status='exported')

    def _import(self, text):
        from plugins.installed.dsers.services.tracking import import_tracking

        return import_tracking(text)

    def test_a_tracking_row_ships_the_order_with_a_fulfillment(self):
        from plugins.installed.dsers.models import OrderSync
        from plugins.installed.orders.models import Fulfillment

        fired = []
        event = MorpheusEvents.ORDER_FULFILLED
        previous = list(hook_registry._handlers.get(event, []))
        hook_registry.register(event, lambda order=None, **kw: fired.append(order.pk))
        self.addCleanup(hook_registry._handlers.__setitem__, event, previous)

        result = self._import(CSV.format(number=self.order.order_number))

        self.assertEqual(result['shipped'], [self.order.order_number], result)
        self.order = type(self.order).objects.get(
            pk=self.order.pk
        )  # status is a protected FSM field
        self.assertEqual(self.order.status, 'shipped')
        self.assertEqual(self.order.tracking_number, 'LP123456789CN')
        f = Fulfillment.objects.get(order=self.order)
        self.assertEqual(f.status, 'in_transit')
        self.assertEqual(f.carrier, 'AliExpress Standard Shipping')
        self.assertEqual(f.tracking_url, 'https://t.17track.net/en#nums=LP123456789CN')
        self.assertEqual(sum(i.quantity for i in f.items.all()), 2)
        sync = OrderSync.objects.get(order=self.order)
        self.assertEqual(sync.status, 'shipped')
        self.assertEqual(sync.supplier_order_number, '8172635401234567')
        self.assertEqual(sync.tracking_number, 'LP123456789CN')
        self.assertEqual(fired, [self.order.pk])  # the "on its way" email, once

    def test_headers_are_matched_tolerantly(self):
        text = f'order no,tracking no\n#{self.order.order_number},LP000000001CN\n'
        result = self._import(text)
        self.assertEqual(result['shipped'], [self.order.order_number], result)
        self.order = type(self.order).objects.get(
            pk=self.order.pk
        )  # status is a protected FSM field
        self.assertEqual(self.order.tracking_number, 'LP000000001CN')

    def test_unknown_order_and_missing_tracking_are_reported_not_raised(self):
        text = f'Order number,Tracking number\nNOPE-1,LP1CN\n{self.order.order_number},\n'
        result = self._import(text)
        self.assertEqual(result['shipped'], [])
        self.assertEqual(result['unknown'], ['NOPE-1'])
        self.assertEqual(result['skipped'], [(self.order.order_number, 'no tracking number')])

    def test_an_already_shipped_order_is_skipped(self):
        self.order.ship(tracking_number='OLD1')
        self.order.save()
        result = self._import(CSV.format(number=self.order.order_number))
        self.assertEqual(result['skipped'], [(self.order.order_number, 'already shipped')])
        self.order = type(self.order).objects.get(
            pk=self.order.pk
        )  # status is a protected FSM field
        self.assertEqual(self.order.tracking_number, 'OLD1')

    def test_a_file_without_the_two_columns_is_an_error(self):
        from plugins.installed.dsers.services.tracking import TrackingImportError

        with self.assertRaises(TrackingImportError):
            self._import('foo,bar\n1,2\n')
