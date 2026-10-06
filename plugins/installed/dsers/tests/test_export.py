"""Orders leave for DSers as the `import_orders` CSV, shaped the way DSers reads it.

DSers' CSV order template is strict: twenty-one columns in a fixed order, the
full country name (a code is rejected), no special characters in the address,
a phone of digits and `+` only. Only paid, shippable, not-yet-exported orders
go out, and an export leaves a mark so the same order never ships twice.
"""

from __future__ import annotations

import csv
import io

from django.test import TestCase

from plugins.installed.dsers.tests._fixtures import digital_product, paid_order, physical_product


class EligibilityTests(TestCase):
    def setUp(self):
        from plugins.installed.dsers.models import OrderSync

        self.product, self.variant = physical_product()
        self.ebook, self.pdf = digital_product()
        self.eligible = paid_order([(self.product, self.variant, 2)])
        self.unpaid = paid_order([(self.product, self.variant, 1)])
        self.unpaid.payment_status = 'unpaid'
        self.unpaid.save(update_fields=['payment_status'])
        self.cancelled = paid_order([(self.product, self.variant, 1)], status='cancelled')
        self.digital_only = paid_order([(self.ebook, self.pdf, 1)])
        self.exported = paid_order([(self.product, self.variant, 1)])
        OrderSync.objects.create(order=self.exported, status='exported')

    def test_only_paid_shippable_unexported_orders_are_eligible(self):
        from plugins.installed.dsers.services.export import eligible_orders

        self.assertEqual([o.pk for o in eligible_orders()], [self.eligible.pk])


class OrdersCsvTests(TestCase):
    def setUp(self):
        from plugins.registry import app_registry

        self.plugin = app_registry.get('dsers')
        self.plugin.set_config('order_memo', 'No invoice or promotions in the parcel')
        self.plugin.set_config('mark_processing_on_export', True)
        self.addCleanup(self.plugin.invalidate_config_cache)
        self.product, self.variant = physical_product()
        self.ebook, self.pdf = digital_product()
        # A mixed order: the digital line must not become a DSers row.
        self.order = paid_order([(self.product, self.variant, 2), (self.ebook, self.pdf, 1)])

    def _rows(self):
        from plugins.installed.dsers.services.export import export_orders

        text = export_orders([self.order])
        return list(csv.reader(io.StringIO(text)))

    def test_header_is_the_dsers_template_in_order(self):
        from plugins.installed.dsers.services.export import ORDER_COLUMNS

        header = self._rows()[0]
        self.assertEqual(header, list(ORDER_COLUMNS))
        self.assertEqual(
            header[:6], ['Order number', 'Date', 'Country', 'Product id', 'SKU', 'Product count']
        )
        self.assertEqual(header[-1], 'Passport Number')
        self.assertEqual(len(header), 21)

    def test_one_row_per_physical_line_with_normalised_address(self):
        from plugins.installed.dsers.services.export import ORDER_COLUMNS

        rows = self._rows()
        self.assertEqual(len(rows), 2, rows)  # header + the candle line; the ebook is skipped
        row = dict(zip(ORDER_COLUMNS, rows[1], strict=True))
        self.assertEqual(row['Order number'], self.order.order_number)
        from django.utils import timezone

        self.assertEqual(row['Date'], timezone.localtime(self.order.placed_at).strftime('%Y-%m-%d'))
        self.assertEqual(row['Country'], 'Serbia')  # the code 'RS' expanded
        self.assertEqual(row['Product id'], str(self.product.id))
        self.assertEqual(row['SKU'], self.variant.sku)
        self.assertEqual(row['Product count'], '2')
        self.assertEqual(row['Order memo'], 'No invoice or promotions in the parcel')
        self.assertEqual(row['Contact person'], 'Jelena Petrović')
        self.assertEqual(row['Mobile no'], '+38164123456')
        self.assertEqual(row['Email'], 'jelena@example.com')
        self.assertEqual(row['Address'], 'Ul. Kralja Petra 12/3 stan 5')
        self.assertEqual(row['Province'], 'Central Serbia')
        self.assertEqual(row['City'], 'Beograd')
        self.assertEqual(row['Zip'], '11000')
        self.assertEqual(row['RUT'], '')

    def test_a_full_country_name_passes_through(self):
        from plugins.installed.dsers.services.export import country_name

        self.assertEqual(country_name('United States'), 'United States')
        self.assertEqual(country_name('US'), 'United States')
        self.assertEqual(country_name('de'), 'Germany')
        self.assertEqual(country_name(''), '')

    def test_export_marks_the_order_and_moves_it_to_processing(self):
        from plugins.installed.dsers.models import OrderSync
        from plugins.installed.dsers.services.export import eligible_orders, export_orders

        self.assertEqual(self.order.status, 'confirmed')
        export_orders([self.order])
        sync = OrderSync.objects.get(order=self.order)
        self.assertEqual(sync.status, 'exported')
        self.assertIsNotNone(sync.exported_at)
        self.order = type(self.order).objects.get(
            pk=self.order.pk
        )  # status is a protected FSM field
        self.assertEqual(self.order.status, 'processing')
        self.assertEqual(list(eligible_orders()), [])  # never exported twice

    def test_processing_move_is_a_setting(self):
        self.plugin.set_config('mark_processing_on_export', False)
        from plugins.installed.dsers.services.export import export_orders

        export_orders([self.order])
        self.order = type(self.order).objects.get(
            pk=self.order.pk
        )  # status is a protected FSM field
        self.assertEqual(self.order.status, 'confirmed')


class ProductsCsvTests(TestCase):
    def test_mapping_csv_lists_every_supplier_link(self):
        from plugins.installed.dsers.models import SupplierLink
        from plugins.installed.dsers.services.export import PRODUCT_COLUMNS, export_products

        product, variant = physical_product()
        SupplierLink.objects.create(
            product=product,
            variant=variant,
            supplier_url='https://www.aliexpress.com/item/1005001234567890.html',
            supplier_sku='Color:Black;Size:M',
        )
        rows = list(csv.reader(io.StringIO(export_products())))
        self.assertEqual(rows[0], list(PRODUCT_COLUMNS))
        self.assertEqual(rows[0], ['Product id', 'SKU', 'Supplier url', 'Supplier SKU'])
        self.assertEqual(
            rows[1],
            [
                str(product.id),
                variant.sku,
                'https://www.aliexpress.com/item/1005001234567890.html',
                'Color:Black;Size:M',
            ],
        )
