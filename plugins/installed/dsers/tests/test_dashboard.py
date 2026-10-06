"""The DSers dashboard page, its two downloads and the tracking upload."""

from __future__ import annotations

from django.test import TestCase

from plugins.installed.dsers.tests._fixtures import paid_order, physical_product, staff_user


class DashboardTests(TestCase):
    def setUp(self):
        self.client.force_login(staff_user())
        self.product, self.variant = physical_product()
        self.order = paid_order([(self.product, self.variant, 1)])

    def test_page_lists_orders_awaiting_export_and_unmapped_products(self):
        response = self.client.get('/dashboard/apps/dsers/orders/')
        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        self.assertIn(self.order.order_number, body)
        self.assertIn('Candle', body)  # flagged: no supplier link yet

    def test_orders_export_downloads_the_dsers_csv_and_marks_the_order(self):
        from plugins.installed.dsers.models import OrderSync

        response = self.client.get('/dashboard/dsers/export/orders/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'].split(';')[0], 'text/csv')
        self.assertIn('import_orders', response['Content-Disposition'])
        self.assertIn(self.order.order_number, response.content.decode())
        self.assertTrue(OrderSync.objects.filter(order=self.order, status='exported').exists())

    def test_products_export_downloads_the_mapping_csv(self):
        from plugins.installed.dsers.models import SupplierLink

        SupplierLink.objects.create(
            product=self.product,
            variant=self.variant,
            supplier_url='https://a.li/x',
            supplier_sku='',
        )
        response = self.client.get('/dashboard/dsers/export/products/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('import_products', response['Content-Disposition'])
        self.assertIn('https://a.li/x', response.content.decode())

    def test_tracking_upload_ships_and_reports(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        self.client.get('/dashboard/dsers/export/orders/')
        upload = SimpleUploadedFile(
            'orders.csv',
            f'Order number,Tracking number\n{self.order.order_number},LP9CN\n'.encode(),
            content_type='text/csv',
        )
        response = self.client.post('/dashboard/dsers/import/tracking/', {'csv': upload})
        self.assertEqual(response.status_code, 200)
        self.assertIn('LP9CN', response.content.decode())
        self.order = type(self.order).objects.get(
            pk=self.order.pk
        )  # status is a protected FSM field
        self.assertEqual(self.order.status, 'shipped')

    def test_non_staff_cannot_download_orders(self):
        self.client.logout()
        response = self.client.get('/dashboard/dsers/export/orders/')
        self.assertIn(response.status_code, (302, 403))
