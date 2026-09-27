"""Server-side GA4 events: built from real data, sent off the request thread.

`view_item` never reached GA4 on any store: the product page fires
PRODUCT_VIEWED with a row loaded `.only('id', 'slug', …)`, and djmoney raises
KeyError (not AttributeError) when a deferred MoneyField is read, so
`getattr(product, 'price', None)` raised and every build failed ("builder
failed: 'price'", thousands of times a day). dotbooks has GA4 configured and
sending — and had zero view_item events.

Making it work had three consequences to handle: ~90% of product-page hits are
crawlers, which Measurement Protocol cannot filter (it never sees the
visitor's user agent); `send_event` POSTs to Google synchronously, which would
have put a Google round-trip on every product page; and line items reported
the catalog price instead of what the line was charged.
"""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase
from djmoney.money import Money

from plugins.installed.catalog.models import Product, ProductVariant

_SEND = 'plugins.installed.tracking.services.measurement_protocol.send_event'
_BROWSER = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Safari/605.1.15'


def _sent(mock_send, event_name):
    return [c.kwargs for c in mock_send.call_args_list if c.kwargs.get('event_name') == event_name]


class ViewItemFromProductPageTests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(
            name='Lavender Oil',
            slug='lavender-oil-probe',
            sku='LAV-1',
            price=Money(Decimal('12.50'), 'USD'),
            product_type='simple',
            status='active',
        )

    def test_product_page_sends_view_item_with_its_price(self):
        with patch(_SEND) as send:
            resp = self.client.get('/products/lavender-oil-probe/', HTTP_USER_AGENT=_BROWSER)
        self.assertEqual(resp.status_code, 200)
        [call] = _sent(send, 'view_item')
        self.assertEqual(call['params']['value'], 12.5)
        self.assertEqual(call['params']['currency'], 'USD')
        self.assertEqual(call['params']['items'][0]['item_id'], 'LAV-1')
        self.assertEqual(call['params']['items'][0]['item_name'], 'Lavender Oil')

    def test_variable_product_reports_the_price_the_page_shows(self):
        product = Product.objects.create(
            name='Rose Water',
            slug='rose-water-probe',
            sku='ROSE',
            price=Money(Decimal('0'), 'USD'),
            product_type='variable',
            status='active',
        )
        ProductVariant.objects.create(
            product=product, name='100ml', sku='ROSE-100', price=Money(Decimal('9.00'), 'USD')
        )
        with patch(_SEND) as send:
            self.client.get('/products/rose-water-probe/', HTTP_USER_AGENT=_BROWSER)
        [call] = _sent(send, 'view_item')
        self.assertEqual(call['params']['value'], 9.0)

    def test_crawlers_are_not_sent_to_ga4(self):
        for ua in (
            'Mozilla/5.0 (compatible; SemrushBot/7~bl; +http://www.semrush.com/bot.html)',
            'Mozilla/5.0 AppleWebKit/537.36 (compatible; PetalBot;+https://webmaster.petalsearch.com/)',
            '',
        ):
            with self.subTest(ua=ua), patch(_SEND) as send:
                self.client.get('/products/lavender-oil-probe/', HTTP_USER_AGENT=ua)
                self.assertEqual(_sent(send, 'view_item'), [])

    def test_the_send_is_queued_not_run_in_the_request(self):
        with patch('plugins.installed.tracking.tasks.send_event_task.delay') as delay:
            self.client.get('/products/lavender-oil-probe/', HTTP_USER_AGENT=_BROWSER)
        self.assertEqual(delay.call_count, 1)
        self.assertEqual(delay.call_args.kwargs['event_name'], 'view_item')


class ChargedLinePriceTests(TestCase):
    """Items carry the price the line was charged, not today's catalog price."""

    def setUp(self):
        self.product = Product.objects.create(
            name='Book',
            slug='book-lines',
            sku='BK',
            price=Money(Decimal('10.00'), 'USD'),
            product_type='simple',
            status='active',
        )

    def _line(self, unit_price):
        return SimpleNamespace(
            product=self.product, variant=None, quantity=2, unit_price=unit_price
        )

    def test_purchase_items_use_the_line_unit_price(self):
        from plugins.installed.tracking.services import event_mapping

        order = SimpleNamespace(
            pk=1,
            order_number='ORD-1',
            items=SimpleNamespace(all=lambda: [self._line(Money(Decimal('7.25'), 'USD'))]),
            total=Money(Decimal('14.50'), 'USD'),
            shipping_total=None,
            tax_total=None,
            metadata={},
        )
        _, params = event_mapping.purchase(order)
        self.assertEqual(params['items'][0]['price'], 7.25)

    def test_begin_checkout_values_the_cart_at_its_line_prices(self):
        from plugins.installed.tracking.services import event_mapping

        cart = SimpleNamespace(
            items=SimpleNamespace(all=lambda: [self._line(Money(Decimal('8.00'), 'EUR'))])
        )
        _, params = event_mapping.begin_checkout(cart)
        self.assertEqual(params['items'][0]['price'], 8.0)
        self.assertEqual(params['value'], 16.0)
        self.assertEqual(params['currency'], 'EUR')
