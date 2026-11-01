"""An order's printed documents: the invoice says who sold it, the packing slip
says what goes in the box.

The invoice printed only the store's name, email and phone: no business
address and no VAT number, which an invoice in most of the world must carry,
and one "Tax" line whatever rates checkout applied. There was no packing slip,
so a store printed the invoice, prices and all, to pack a gift.
"""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from djmoney.money import Money

from morpheus.core import ToolError
from plugins.installed.catalog.models import Product
from plugins.installed.orders.agent_tools import orders_documents_tool
from plugins.installed.orders.models import Fulfillment, FulfillmentItem, Order, OrderItem
from plugins.models import PluginConfig
from plugins.registry import app_registry

_ADDRESS = {
    'first_name': 'Ana',
    'last_name': 'Kovač',
    'address_line1': '1 Main Street',
    'city': 'Belgrade',
    'postal_code': '11000',
    'country': 'RS',
}


def _money(amount: str) -> Money:
    return Money(Decimal(amount), 'EUR')


class _OrderFixture(TestCase):
    def setUp(self):
        staff = get_user_model().objects.create_user(
            username='packer', email='packer@example.com', password='x', is_staff=True
        )
        self.client.force_login(staff)
        self.order = Order.objects.create(
            email='buyer@example.com',
            subtotal=_money('30.00'),
            tax_total=_money('6.00'),
            total=_money('36.00'),
            payment_gateway='stripe',
            shipping_method='Standard post',
            shipping_address=_ADDRESS,
            customer_notes='It is a gift',
            metadata={'tax_lines': [{'label': 'PDV 20%', 'amount': '6.00'}]},
        )
        book = Product.objects.create(
            name='Boxed Atlas', slug='boxed-atlas', sku='ATLAS-1', price=_money('10.00')
        )
        ebook = Product.objects.create(
            name='Atlas eBook',
            slug='atlas-ebook',
            sku='ATLAS-E',
            price=_money('10.00'),
            requires_shipping=False,
        )
        self.atlas = OrderItem.objects.create(
            order=self.order,
            product=book,
            product_name='Boxed Atlas',
            sku='ATLAS-1',
            quantity=2,
            unit_price=_money('10.00'),
            total_price=_money('20.00'),
        )
        self.ebook = OrderItem.objects.create(
            order=self.order,
            product=ebook,
            product_name='Atlas eBook',
            sku='ATLAS-E',
            quantity=1,
            unit_price=_money('10.00'),
            total_price=_money('10.00'),
        )
        self.base = f'/dashboard/orders/{self.order.order_number}/'

    def _config(self, **values):
        PluginConfig.objects.update_or_create(plugin_name='orders', defaults={'config': values})
        self.addCleanup(app_registry.get('orders').invalidate_config_cache)

    def _body(self, path: str) -> str:
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200, path)
        return response.content.decode()


class InvoiceTests(_OrderFixture):
    def test_the_seller_is_the_business_set_in_settings(self):
        self._config(
            invoice_business_name='Atlas Books d.o.o.',
            invoice_address='Knez Mihailova 1, 11000 Beograd, Serbia',
            invoice_tax_id='PIB 123456789',
        )
        body = self._body(f'{self.base}invoice/')
        for text in ('Atlas Books d.o.o.', 'Knez Mihailova 1', 'PIB 123456789'):
            with self.subTest(text=text):
                self.assertIn(text, body)
        self.assertNotIn('data-seller-missing', body)

    def test_without_business_details_the_store_name_prints_and_staff_are_told(self):
        body = self._body(f'{self.base}invoice/')
        self.assertIn('data-seller-missing', body)
        self.assertIn('/dashboard/settings/orders/', body)

    def test_each_tax_rate_is_its_own_line(self):
        body = self._body(f'{self.base}invoice/')
        self.assertIn('data-tax-line', body)
        self.assertIn('PDV 20%', body)

    def test_an_order_without_rates_prints_one_tax_line(self):
        self.order.metadata = {}
        self.order.save(update_fields=['metadata'])
        body = self._body(f'{self.base}invoice/')
        self.assertNotIn('data-tax-line', body)
        self.assertIn('<td>Tax</td>', body)


class PackingSlipTests(_OrderFixture):
    def test_the_slip_lists_what_to_pack_without_prices(self):
        body = self._body(f'{self.base}packing-slip/')
        self.assertIn('data-slip-covers="open"', body)
        self.assertIn('Boxed Atlas', body)
        self.assertIn('Standard post', body)
        self.assertIn('It is a gift', body)
        self.assertNotIn('€', body)
        self.assertNotIn('10.00', body)

    def test_a_digital_item_is_counted_not_packed(self):
        body = self._body(f'{self.base}packing-slip/')
        self.assertEqual(body.count('data-slip-line'), 1)
        self.assertNotIn('Atlas eBook', body)
        self.assertIn('data-not-packed', body)

    def test_a_shipment_slip_lists_that_shipment(self):
        shipment = Fulfillment.objects.create(
            order=self.order,
            carrier='Post Express',
            tracking_number='PE123',
            shipped_at=timezone.now(),
        )
        FulfillmentItem.objects.create(fulfillment=shipment, order_item=self.atlas, quantity=1)
        body = self._body(f'{self.base}packing-slip/?fulfillment={shipment.pk}')
        self.assertIn('data-slip-covers="shipment"', body)
        self.assertIn('Post Express', body)
        self.assertIn('PE123', body)
        self.assertIn('<strong>1</strong>', body)

    def test_once_everything_is_sent_the_slip_is_the_whole_order(self):
        OrderItem.objects.filter(pk=self.atlas.pk).update(fulfilled_quantity=2)
        OrderItem.objects.filter(pk=self.ebook.pk).update(fulfilled_quantity=1)
        body = self._body(f'{self.base}packing-slip/')
        self.assertIn('data-slip-covers="all"', body)
        self.assertIn('<strong>2</strong>', body)

    def test_a_shipment_of_another_order_or_a_bad_id_is_not_found(self):
        other = Order.objects.create(
            email='x@example.com', subtotal=_money('1.00'), total=_money('1.00')
        )
        foreign = Fulfillment.objects.create(order=other)
        for wanted in (foreign.pk, 'not-a-uuid'):
            with self.subTest(wanted=wanted):
                response = self.client.get(f'{self.base}packing-slip/?fulfillment={wanted}')
                self.assertEqual(response.status_code, 404)


class DocumentLinksTests(_OrderFixture):
    def test_the_order_and_fulfil_pages_link_the_slip(self):
        Fulfillment.objects.create(order=self.order)
        slip = f'{self.base}packing-slip/'
        detail = self._body(self.base)
        self.assertIn(f'href="{slip}"', detail)
        self.assertIn(f'href="{slip}?fulfillment=', detail)
        self.assertIn(f'href="{slip}"', self._body(f'{self.base}fulfill/'))


class DocumentAccessTests(_OrderFixture):
    def test_only_staff_open_them(self):
        shopper = get_user_model().objects.create_user(
            username='shopper', email='shopper@example.com', password='x'
        )
        for user in (None, shopper):
            if user is None:
                self.client.logout()
            else:
                self.client.force_login(user)
            for page in ('invoice/', 'packing-slip/'):
                with self.subTest(user=user, page=page):
                    response = self.client.get(f'{self.base}{page}')
                    self.assertEqual(response.status_code, 302)
                    self.assertNotIn('Boxed Atlas', response.content.decode())


class DocumentsToolTests(_OrderFixture):
    def test_linda_gets_both_links(self):
        out = orders_documents_tool.invoke({'order_number': self.order.order_number}).output
        self.assertTrue(out['invoice_url'].endswith(f'{self.base}invoice/'))
        self.assertTrue(out['packing_slip_url'].endswith(f'{self.base}packing-slip/'))

    def test_an_unknown_order_is_an_error(self):
        with self.assertRaises(ToolError):
            orders_documents_tool.invoke({'order_number': 'MRP00000000'})

    def test_the_tool_only_reads(self):
        self.assertEqual(orders_documents_tool.scopes, ['orders.read'])
        self.assertFalse(orders_documents_tool.requires_approval)
