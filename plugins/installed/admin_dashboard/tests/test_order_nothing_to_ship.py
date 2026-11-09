"""An order of downloads only offers no fulfilment: nothing ships, so nothing is
tracked. Until v0.148.0 the owner delivered a PDF by creating a shipment."""

# ruff: noqa: PLC0415
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.test import TestCase
from djmoney.money import Money


class NothingToShipTests(TestCase):
    def setUp(self):
        from plugins.installed.catalog.models import Product

        staff = get_user_model().objects.create_user(
            username='ops', email='ops@example.com', password='x', is_staff=True, is_superuser=True
        )
        self.client.force_login(staff)
        self.ebook = Product.objects.create(
            name='The Long Road',
            slug='nts-ebook',
            sku='NTS-1',
            product_type='digital',
            price=Money(8, 'USD'),
        )
        self.ebook.digital_file.save('long-road.pdf', ContentFile(b'%PDF-1.4'), save=True)
        self.mug = Product.objects.create(
            name='Mug', slug='nts-mug', sku='NTS-2', price=Money(5, 'USD')
        )

    def _order(self, *products):
        from plugins.installed.orders.models import Order, OrderItem

        buyer = get_user_model().objects.create_user(
            username=f'b{Order.objects.count()}@example.com', password='x'
        )
        order = Order.objects.create(
            customer=buyer,
            email='b@example.com',
            subtotal=Money(8, 'USD'),
            total=Money(8, 'USD'),
            status='processing',
            payment_status='paid',
        )
        for product in products:
            OrderItem.objects.create(
                order=order,
                product=product,
                product_name=product.name,
                sku=product.sku,
                quantity=1,
                unit_price=Money(8, 'USD'),
                total_price=Money(8, 'USD'),
            )
        return order

    def _page(self, order):
        response = self.client.get(f'/dashboard/orders/{order.order_number}/')
        self.assertEqual(response.status_code, 200)
        return response.content.decode()

    def test_downloads_only_offer_no_fulfilment(self):
        body = self._page(self._order(self.ebook))
        self.assertNotIn('Create fulfillment', body)
        self.assertNotIn('Add fulfillment', body)
        self.assertIn('Nothing to ship', body)
        self.assertIn('Download ready', body)

    def test_a_parcel_still_gets_its_fulfilment(self):
        body = self._page(self._order(self.ebook, self.mug))
        self.assertIn('Create fulfillment', body)

    def test_switched_off_downloads_app_keeps_the_fulfilment(self):
        # The promise is the digital_products app's to make: without it nothing
        # issues the links, so the page offers the fulfilment form as before.
        from plugins.registry import app_registry

        app_registry.deactivate('digital_products')
        self.addCleanup(app_registry.activate, 'digital_products')
        body = self._page(self._order(self.ebook))
        self.assertIn('Create fulfillment', body)
        self.assertNotIn('Nothing to ship', body)
