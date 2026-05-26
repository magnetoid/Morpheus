"""Smoke + unit tests for the bookvault services layer.

Network is patched at the requests.get / requests.post boundary so
nothing actually hits *.bookvault.app during tests.
"""
from __future__ import annotations

import json
from decimal import Decimal
from unittest.mock import patch, MagicMock

from django.test import TestCase
from djmoney.money import Money

from plugins.installed.bookvault import services
from plugins.installed.bookvault.models import (
    BookvaultOrderLink, BookvaultProductLink,
)
from plugins.installed.catalog.models import Product
from plugins.installed.orders.models import Order


def _seed_config(**overrides):
    """Helper: write a fake PluginConfig so the API client behaves as configured."""
    from plugins.models import PluginConfig
    cfg, _ = PluginConfig.objects.update_or_create(
        plugin_name='bookvault',
        defaults={'is_enabled': True},
    )
    base = {
        'token': 'tok-test',
        'store_id': '42',
        'authenticated': True,
        'auto_send_on_paid': True,
    }
    base.update(overrides)
    cfg.config = base
    cfg.save()
    return cfg


class IsbnLineExtractionTests(TestCase):
    """Only 13-digit SKUs are sent to BV — that's the WP plugin's contract."""

    def test_skips_non_13_char_sku(self):
        class FakeItem:
            quantity = 2
            product = type('P', (), {'sku': 'SHORTSKU'})()
            variant = None
        class FakeCart:
            class items:
                @staticmethod
                def all():
                    return [FakeItem()]
        self.assertEqual(services._isbn_lines(FakeCart()), [])

    def test_keeps_13_char_sku(self):
        class FakeItem:
            quantity = 3
            product = type('P', (), {'sku': '9781234567890'})()
            variant = None
        class FakeCart:
            class items:
                @staticmethod
                def all():
                    return [FakeItem()]
        self.assertEqual(
            services._isbn_lines(FakeCart()),
            [{'ISBN': '9781234567890', 'Quantity': 3}],
        )


class ShippingRatesTests(TestCase):
    """get_shipping_rates: empty input → empty output (no API hit);
    happy path → normalised list."""

    def test_empty_lines_returns_empty(self):
        # Even with country set, an empty cart shouldn't generate a request.
        with patch.object(services.requests, 'post') as mocked:
            out = services.get_shipping_rates(
                order_lines=[], country_code='US', postcode='10001',
            )
        self.assertEqual(out, [])
        mocked.assert_not_called()

    def test_normalised_output_shape(self):
        fake_resp = MagicMock()
        fake_resp.status_code = 200
        fake_resp.content = b'x'
        fake_resp.json.return_value = {'Services': [
            {'ServID': 'STD', 'ServName': 'Standard',
             'ServDetail': '5-7 days', 'DelTotal': '4.99'},
            {'ServID': 'EXP', 'ServName': 'Express',
             'ServDetail': '2 days', 'DelTotal': '12.50'},
        ]}
        fake_resp.raise_for_status = MagicMock()
        with patch.object(services.requests, 'post', return_value=fake_resp):
            out = services.get_shipping_rates(
                order_lines=[{'ISBN': '9781234567890', 'Quantity': 1}],
                country_code='gb', postcode='SW1A 1AA',
            )
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0]['id'], 'STD')
        self.assertEqual(out[0]['amount'], Decimal('4.99'))
        self.assertEqual(out[1]['amount'], Decimal('12.50'))


class AuthenticateTests(TestCase):
    """authenticate() persists Token/StoreID/Authenticated into PluginConfig."""

    def test_happy_path_writes_config(self):
        fake = MagicMock()
        fake.status_code = 200
        fake.content = b'x'
        fake.json.return_value = {
            'Token': 'new-tok', 'StoreID': 99, 'Authenticated': True,
        }
        fake.raise_for_status = MagicMock()
        with patch.object(services.requests, 'get', return_value=fake):
            data = services.authenticate(store_url_override='https://example.test/')
        self.assertEqual(data['Token'], 'new-tok')
        cfg = services._config()
        self.assertEqual(cfg['token'], 'new-tok')
        self.assertEqual(cfg['store_id'], '99')
        self.assertTrue(cfg['authenticated'])

    def test_request_failure_returns_error(self):
        from requests import RequestException
        with patch.object(services.requests, 'get', side_effect=RequestException('boom')):
            data = services.authenticate(store_url_override='https://example.test/')
        self.assertIn('error', data)
        # Config must NOT have been written for the failed handshake.
        self.assertFalse(services.is_authenticated())


class SendOrderTests(TestCase):
    """send_order: writes a BookvaultOrderLink row + captures BVRef."""

    def setUp(self):
        _seed_config()
        product = Product.objects.create(
            name='Test Book', slug='test-book-bv', sku='9781234567890',
            status='active', price=Money(Decimal('10.00'), 'USD'),
            product_type='digital',
        )
        self.order = Order.objects.create(
            email='customer@example.com',
            subtotal=Money(Decimal('10.00'), 'USD'),
            total=Money(Decimal('12.99'), 'USD'),
        )
        # Items can be empty — _order_payload tolerates an empty list,
        # and we only need to assert the network call shape.

    def test_writes_bv_ref_to_link_row(self):
        fake = MagicMock()
        fake.content = b'x'
        fake.json.return_value = {'BVRef': 'BV-12345'}
        fake.raise_for_status = MagicMock()
        with patch.object(services.requests, 'post', return_value=fake):
            out = services.send_order(order=self.order)
        self.assertEqual(out.get('BVRef'), 'BV-12345')
        link = BookvaultOrderLink.objects.get(order=self.order)
        self.assertEqual(link.bv_ref, 'BV-12345')

    def test_skips_when_disabled(self):
        _seed_config(auto_send_on_paid=False)
        with patch.object(services.requests, 'post') as mocked:
            out = services.send_order(order=self.order)
        self.assertEqual(out, {'skipped': 'auto_send_on_paid disabled'})
        mocked.assert_not_called()

    def test_no_config_returns_error(self):
        # Wipe the config row so the auth gate kicks in.
        from plugins.models import PluginConfig
        PluginConfig.objects.filter(plugin_name='bookvault').delete()
        out = services.send_order(order=self.order)
        self.assertIn('error', out)


class ProductLinkStatusTests(TestCase):
    """product_link_status: Linked / Partial / Unlinked aggregate."""

    def setUp(self):
        self.product = Product.objects.create(
            name='Status Test', slug='status-test',
            sku='9789999999999', status='active',
            price=Money(Decimal('10.00'), 'USD'),
            product_type='simple',
        )

    def test_no_links_yet_returns_unlinked(self):
        self.assertEqual(services.product_link_status(self.product), 'Unlinked')

    def test_linked_returns_linked(self):
        BookvaultProductLink.objects.create(
            product=self.product, variant=None,
            locations=[1, 3], is_linked=True,
        )
        self.assertEqual(services.product_link_status(self.product), 'Linked')
