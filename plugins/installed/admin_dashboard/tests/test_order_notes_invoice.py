"""The order page carries notes and a printable invoice.

``Order.staff_notes`` and ``customer_notes`` existed but the order page never
showed or edited them, the shipping address printed as a raw Python dict, and
there was no invoice to print.
"""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from djmoney.money import Money

from plugins.installed.orders.models import Order


class OrderNotesInvoiceTests(TestCase):
    def setUp(self):
        staff = get_user_model().objects.create_user(
            username='ops', email='ops@example.com', password='x', is_staff=True
        )
        self.client.force_login(staff)
        self.order = Order.objects.create(
            email='buyer@example.com',
            subtotal=Money(Decimal('8.00'), 'USD'),
            total=Money(Decimal('9.50'), 'USD'),
            customer_notes='Leave it at the door',
            payment_gateway='cod',
            shipping_address={
                'first_name': 'Ana',
                'last_name': 'Kovač',
                'address_line1': '1 Main Street',
                'city': 'Belgrade',
                'postal_code': '11000',
                'country': 'RS',
            },
            metadata={'extras': [{'label': 'Plant a tree', 'amount': '1.50'}]},
        )
        self.url = f'/dashboard/orders/{self.order.order_number}/'

    def test_staff_notes_are_saved_and_shown(self):
        response = self.client.post(f'{self.url}notes/', {'staff_notes': 'Called the customer'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Order.objects.get(pk=self.order.pk).staff_notes, 'Called the customer')
        body = self.client.get(self.url).content.decode()
        self.assertIn('Called the customer', body)
        self.assertIn('Leave it at the door', body)

    def test_the_address_is_lines_not_a_dict(self):
        body = self.client.get(self.url).content.decode()
        self.assertIn('1 Main Street', body)
        self.assertNotIn('address_line1', body)

    def test_the_invoice_lists_every_total_line(self):
        response = self.client.get(f'{self.url}invoice/')
        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        for text in ('Invoice', self.order.order_number, 'Cash on delivery', 'Plant a tree',
                     '$1.50', '$9.50', '1 Main Street'):  # fmt: skip
            with self.subTest(text=text):
                self.assertIn(text, body)
