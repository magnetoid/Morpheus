"""The shared supplier machinery in ``plugins.dropshipping``.

Behaviour the supplier apps rely on without owning: country expansion, address
cleaning, header-tolerant tracking files, and the state-machine walk that ships
an order from wherever it is.
"""

from __future__ import annotations

from decimal import Decimal

from django.test import SimpleTestCase, TestCase
from djmoney.money import Money

from plugins.dropshipping import (
    TrackingCsvError,
    clean_phone,
    clean_text,
    country_name,
    parse_tracking_rows,
    ship_with_tracking,
)


class NormalisationTests(SimpleTestCase):
    def test_country_codes_expand_and_names_pass_through(self):
        self.assertEqual(country_name('RS'), 'Serbia')
        self.assertEqual(country_name('us'), 'United States')
        self.assertEqual(country_name('Germany'), 'Germany')
        self.assertEqual(country_name('ZZ'), 'ZZ')
        self.assertEqual(country_name(None), '')

    def test_text_and_phone_cleaning(self):
        self.assertEqual(
            clean_text('Ul. Kralja Petra 12/3 — stan 5!'), 'Ul. Kralja Petra 12/3 stan 5'
        )
        self.assertEqual(clean_phone('+381 (64) 123-456'), '+38164123456')
        self.assertEqual(clean_phone('064 123 456'), '064123456')


class TrackingRowsTests(SimpleTestCase):
    def test_headers_are_matched_by_meaning(self):
        rows = parse_tracking_rows(
            'Order Name,Zendrop Order Id,Tracking Number,Shipping Line\n'
            '#1001,ZD-1,LP1CN,YunExpress\n,ZD-2,LP2CN,\n'
        )
        self.assertEqual(
            rows,
            [
                {
                    'order_number': '1001',
                    'tracking': 'LP1CN',
                    'supplier_order_number': 'ZD-1',
                    'carrier': 'YunExpress',
                }
            ],
        )

    def test_a_bom_and_an_aliexpress_export_both_read(self):
        rows = parse_tracking_rows(
            '﻿Order number,AliExpress order number,Tracking number\n7,81726,LP9CN\n'
        )
        self.assertEqual(rows[0]['supplier_order_number'], '81726')

    def test_missing_mandatory_columns_raise(self):
        with self.assertRaises(TrackingCsvError):
            parse_tracking_rows('foo,bar\n1,2\n')


class ShipWithTrackingTests(TestCase):
    def test_ships_from_pending_through_the_whole_machine(self):
        from plugins.installed.catalog.models import Product
        from plugins.installed.orders.models import Fulfillment, Order, OrderItem

        product = Product.objects.create(
            name='Probe',
            slug='ship-probe',
            sku='SHIP-1',
            price=Money(Decimal('5'), 'USD'),
            status='active',
        )
        order = Order.objects.create(
            email='p@example.com',
            subtotal=Money(Decimal('5'), 'USD'),
            total=Money(Decimal('5'), 'USD'),
            payment_status='paid',
        )
        OrderItem.objects.create(
            order=order, product=product, product_name='Probe', sku='SHIP-1', quantity=3,
            unit_price=product.price, total_price=Money(Decimal('15'), 'USD'),
        )  # fmt: skip

        fulfillment = ship_with_tracking(order, 'TRK1', carrier='DHL', url='https://x/TRK1')

        order = Order.objects.get(pk=order.pk)
        self.assertEqual((order.status, order.tracking_number), ('shipped', 'TRK1'))
        self.assertEqual(Fulfillment.objects.get(pk=fulfillment.pk).carrier, 'DHL')
        self.assertEqual(sum(i.quantity for i in fulfillment.items.all()), 3)
        self.assertEqual(order.items.get().fulfilled_quantity, 3)
