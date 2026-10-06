"""Order sheets, "placed" bookkeeping, and shipping with tracking — the platform way."""

from __future__ import annotations

from django.test import TestCase

from morpheus.core import MorpheusEvents, hook_registry
from plugins.installed.zendrop.tests._fixtures import paid_order, physical_product, refetch


class OrderSheetTests(TestCase):
    def setUp(self):
        from plugins.installed.zendrop.models import ZendropLink

        self.product, self.variant = physical_product()
        ZendropLink.objects.create(
            product=self.product,
            variant=self.variant,
            zendrop_product_id='8421',
            zendrop_variant_id='77',
            product_url='https://app.zendrop.com/products/8421',
        )
        self.order = paid_order([(self.product, self.variant, 2)])

    def test_sheet_has_a_supplier_ready_address_and_mapped_lines(self):
        from plugins.installed.zendrop.services.orders import awaiting_orders, order_sheet

        self.assertEqual([o.pk for o in awaiting_orders()], [self.order.pk])
        sheet = order_sheet(self.order)
        self.assertEqual(sheet['address']['country'], 'Serbia')
        self.assertEqual(sheet['address']['phone'], '+38121555123')
        self.assertEqual(sheet['address']['line1'], 'Bulevar Oslobođenja 100 stan 7')
        self.assertEqual(sheet['address']['contact'], 'Mara Jovanović')
        line = sheet['lines'][0]
        self.assertEqual(
            (line['quantity'], line['zendrop_product_id'], line['zendrop_variant_id']),
            (2, '8421', '77'),
        )
        self.assertTrue(line['mapped'])

    def test_an_unmapped_line_is_flagged(self):
        from plugins.installed.zendrop.models import ZendropLink
        from plugins.installed.zendrop.services.orders import order_sheet

        ZendropLink.objects.all().delete()
        self.assertFalse(order_sheet(self.order)['lines'][0]['mapped'])

    def test_marking_placed_records_the_order_and_moves_it_to_processing(self):
        from plugins.installed.zendrop.models import ZendropOrder
        from plugins.installed.zendrop.services.orders import awaiting_orders, mark_placed

        mark_placed(self.order, 'ZD-100200')
        record = ZendropOrder.objects.get(order=self.order)
        self.assertEqual((record.status, record.zendrop_order_number), ('placed', 'ZD-100200'))
        self.assertIsNotNone(record.placed_at)
        self.assertEqual(refetch(self.order).status, 'processing')
        self.assertEqual(awaiting_orders(), [])

    def test_processing_move_is_a_setting(self):
        from plugins.registry import app_registry

        plugin = app_registry.get('zendrop')
        plugin.set_config('mark_processing_when_placed', False)
        self.addCleanup(plugin.invalidate_config_cache)
        from plugins.installed.zendrop.services.orders import mark_placed

        mark_placed(self.order)
        self.assertEqual(refetch(self.order).status, 'confirmed')


class ShipTests(TestCase):
    def setUp(self):
        from plugins.installed.zendrop.services.orders import mark_placed
        from plugins.registry import app_registry

        plugin = app_registry.get('zendrop')
        plugin.set_config('tracking_url_template', 'https://t.17track.net/en#nums={tracking}')
        self.addCleanup(plugin.invalidate_config_cache)
        self.product, self.variant = physical_product()
        self.order = paid_order([(self.product, self.variant, 1)])
        mark_placed(self.order, 'ZD-1')

    def test_ship_order_creates_the_fulfillment_and_fires_fulfilled_once(self):
        from plugins.installed.orders.models import Fulfillment
        from plugins.installed.zendrop.models import ZendropOrder
        from plugins.installed.zendrop.services.orders import ship_order

        fired = []
        event = MorpheusEvents.ORDER_FULFILLED
        previous = list(hook_registry._handlers.get(event, []))
        hook_registry.register(event, lambda order=None, **kw: fired.append(order.pk))
        self.addCleanup(hook_registry._handlers.__setitem__, event, previous)

        self.assertEqual(ship_order(self.order, 'ZD123456789US', 'USPS'), '')

        order = refetch(self.order)
        self.assertEqual((order.status, order.tracking_number), ('shipped', 'ZD123456789US'))
        f = Fulfillment.objects.get(order=order)
        self.assertEqual(
            (f.carrier, f.tracking_url), ('USPS', 'https://t.17track.net/en#nums=ZD123456789US')
        )
        record = ZendropOrder.objects.get(order=order)
        self.assertEqual(
            (record.status, record.tracking_number, record.zendrop_order_number),
            ('shipped', 'ZD123456789US', 'ZD-1'),
        )
        self.assertEqual(fired, [order.pk])

    def test_skips_are_reasons_not_errors(self):
        from plugins.installed.zendrop.services.orders import ship_order

        self.assertEqual(ship_order(self.order, ''), 'no tracking number')
        ship_order(self.order, 'ZD1')
        self.assertEqual(ship_order(self.order, 'ZD2'), 'already shipped')
        self.assertEqual(refetch(self.order).tracking_number, 'ZD1')

    def test_tracking_csv_matches_headers_by_meaning(self):
        from plugins.installed.zendrop.services.orders import import_tracking

        text = f'Order Name,Zendrop Order Id,Tracking Number,Shipping Line\n#{self.order.order_number},ZD-1,ZD9CN,YunExpress\nNOPE,ZD-2,X,\n'
        result = import_tracking(text)
        self.assertEqual(result['shipped'], [self.order.order_number])
        self.assertEqual(result['unknown'], ['NOPE'])
        order = refetch(self.order)
        self.assertEqual(order.tracking_number, 'ZD9CN')

    def test_a_file_without_the_two_columns_is_an_error(self):
        from plugins.installed.zendrop.services.orders import TrackingImportError, import_tracking

        with self.assertRaises(TrackingImportError):
            import_tracking('a,b\n1,2\n')
