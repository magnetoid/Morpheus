"""The fulfil form records one parcel with the units the merchant chose.

The test posts back what a browser builds from the rendered page, edited the
way a merchant would (``test_product_form_roundtrip``'s parser).
"""

# ruff: noqa: PLC0415
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase
from djmoney.money import Money

from plugins.installed.admin_dashboard.tests.test_product_form_roundtrip import _FormDataSet


class FulfilFormTests(TestCase):
    def setUp(self):
        from plugins.installed.catalog.models import Product
        from plugins.installed.orders.models import Order, OrderItem

        staff = get_user_model().objects.create_user(
            username='ops', email='ops@example.com', password='x', is_staff=True, is_superuser=True
        )
        self.client.force_login(staff)
        self.order = Order.objects.create(
            email='b@example.com',
            subtotal=Money(30, 'USD'),
            total=Money(30, 'USD'),
            status='processing',
            payment_status='paid',
        )
        self.lines = {}
        for slug, qty, ships in (('mug', 2, True), ('lamp', 1, True), ('pdf', 1, False)):
            product = Product.objects.create(
                name=slug.title(),
                slug=f'ff-{slug}',
                sku=f'FF-{slug.upper()}',
                price=Money(5, 'USD'),
                requires_shipping=ships,
                product_type='physical' if ships else 'digital',
            )
            self.lines[slug] = OrderItem.objects.create(
                order=self.order,
                product=product,
                product_name=product.name,
                sku=product.sku,
                quantity=qty,
                unit_price=Money(5, 'USD'),
                total_price=Money(5 * qty, 'USD'),
            )
        self.url = f'/dashboard/orders/{self.order.order_number}/fulfill/'

    def _entries(self) -> dict:
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        parser = _FormDataSet('fulfil-form')
        parser.feed(response.content.decode())
        return dict(parser.entries)

    def test_the_page_lists_only_what_ships(self):
        entries = self._entries()
        self.assertEqual(entries[f'qty_{self.lines["mug"].pk}'], '2')
        self.assertEqual(entries[f'qty_{self.lines["lamp"].pk}'], '1')
        self.assertNotIn(f'qty_{self.lines["pdf"].pk}', entries)
        self.assertEqual(entries['mark_shipped'], 'on')

    def test_a_partial_parcel_round_trips(self):
        entries = self._entries()
        entries[f'qty_{self.lines["mug"].pk}'] = '1'
        entries[f'qty_{self.lines["lamp"].pk}'] = '0'
        entries['tracking_number'] = 'TRK-9'
        response = self.client.post(self.url, entries)
        self.assertEqual(response.status_code, 302)
        parcel = self.order.fulfillments.get()
        self.assertEqual(parcel.tracking_number, 'TRK-9')
        self.assertEqual(
            [(fi.order_item_id, fi.quantity) for fi in parcel.items.all()],
            [(self.lines['mug'].pk, 1)],
        )
        from plugins.installed.orders.models import Order

        self.assertEqual(Order.objects.get(pk=self.order.pk).status, 'partially_fulfilled')

    def test_the_whole_form_as_rendered_ships_everything(self):
        response = self.client.post(self.url, self._entries())
        self.assertEqual(response.status_code, 302)
        from plugins.installed.orders.models import Order

        self.assertEqual(Order.objects.get(pk=self.order.pk).status, 'shipped')

    def test_too_many_units_are_refused_and_nothing_is_recorded(self):
        entries = self._entries()
        entries[f'qty_{self.lines["mug"].pk}'] = '5'
        response = self.client.post(self.url, entries)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(self.order.fulfillments.exists())

    def test_an_empty_parcel_is_refused(self):
        entries = self._entries()
        entries[f'qty_{self.lines["mug"].pk}'] = '0'
        entries[f'qty_{self.lines["lamp"].pk}'] = '0'
        response = self.client.post(self.url, entries)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'at least one unit')
        self.assertFalse(self.order.fulfillments.exists())
