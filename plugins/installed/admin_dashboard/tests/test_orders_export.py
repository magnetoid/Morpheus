"""Orders → Export exports orders.

The Export button linked to the product importer's CSV export and the bulk
"export" action redirected there too, so a merchant asking for their orders got
the product catalogue. Both now stream the orders the list is showing.
"""

from __future__ import annotations

import csv
import io
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from djmoney.money import Money

from plugins.installed.orders.models import Order


def _order(email, **extra):
    return Order.objects.create(
        email=email,
        subtotal=Money(Decimal('10.00'), 'USD'),
        total=Money(Decimal('10.00'), 'USD'),
        **extra,
    )


class OrdersExportTests(TestCase):
    def setUp(self):
        staff = get_user_model().objects.create_user(
            username='exporter', email='exporter@example.com', password='x', is_staff=True
        )
        self.client.force_login(staff)
        self.shipped = _order(
            'a@example.com',
            shipping_address={
                'first_name': '=HYPERLINK("x")',
                'last_name': 'Smith',
                'country': 'US',
            },
        )
        Order.objects.filter(pk=self.shipped.pk).update(status='shipped')
        self.pending = _order('b@example.com')

    def _rows(self, response):
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response['Content-Type'].startswith('text/csv'))
        body = b''.join(response.streaming_content).decode()
        return list(csv.reader(io.StringIO(body)))

    def test_export_is_the_orders(self):
        rows = self._rows(self.client.get('/dashboard/orders/export/'))
        self.assertEqual(rows[0][:3], ['Order', 'Placed', 'Status'])
        self.assertEqual(
            {row[0] for row in rows[1:]}, {self.shipped.order_number, self.pending.order_number}
        )

    def test_export_follows_the_list_filters(self):
        rows = self._rows(self.client.get('/dashboard/orders/export/?status=shipped'))
        self.assertEqual([row[0] for row in rows[1:]], [self.shipped.order_number])

    def test_a_formula_typed_by_a_shopper_is_not_run(self):
        rows = self._rows(self.client.get('/dashboard/orders/export/?status=shipped'))
        name = rows[1][rows[0].index('Name')]
        self.assertTrue(name.startswith("'="), name)

    def test_bulk_export_returns_the_selected_orders(self):
        response = self.client.post(
            '/dashboard/orders/bulk/', {'action': 'export', 'ids': [str(self.pending.pk)]}
        )
        rows = self._rows(response)
        self.assertEqual([row[0] for row in rows[1:]], [self.pending.order_number])

    def test_the_list_links_to_the_order_export(self):
        body = self.client.get('/dashboard/orders/?status=shipped').content.decode()
        self.assertIn('/dashboard/orders/export/?status=shipped', body)
        # The old Export button (the sidebar's own Import/Export link stays).
        self.assertNotIn('href="/dashboard/apps/importers/csv/" class="btn"', body)
