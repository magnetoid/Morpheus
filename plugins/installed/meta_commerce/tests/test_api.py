"""Graph/Catalog/Ads/CAPI — no-op unconnected, correct shaping connected (mocked)."""

# ruff: noqa: PLC0415
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from django.test import TestCase

from plugins.installed.meta_commerce.services import ads_api, capi, catalog_api


def _plugin():
    from plugins.registry import plugin_registry

    for attr in ('get', 'get_plugin'):
        fn = getattr(plugin_registry, attr, None)
        if callable(fn):
            try:
                p = fn('meta_commerce')
            except Exception:  # noqa: BLE001
                p = None
            if p is not None:
                return p
    from plugins.installed.meta_commerce.plugin import MetaCommercePlugin

    return MetaCommercePlugin()


def _connect(**extra):
    p = _plugin()
    cfg = {
        'access_token': 'TOK',
        'catalog_id': '555',
        'ad_account_id': '999',
        'pixel_id': '123456789012345',
        **extra,
    }
    for k, v in cfg.items():
        p.set_config(k, v)
    p.invalidate_config_cache()


class _Iso:
    def setUp(self):
        _plugin().invalidate_config_cache()

    def tearDown(self):
        _plugin().invalidate_config_cache()


class NotConnectedTests(_Iso, TestCase):
    def test_catalog_noop(self):
        self.assertEqual(catalog_api.push_products()['reason'], 'not_connected')

    def test_ads_noop(self):
        self.assertEqual(ads_api.campaign_report()['reason'], 'not_connected')

    def test_capi_noop(self):
        self.assertEqual(capi.send_purchase(MagicMock())['reason'], 'not_connected')


class VerifyConnectionTests(_Iso, TestCase):
    def test_no_token(self):
        from plugins.installed.meta_commerce.services.graph import verify_connection

        self.assertFalse(verify_connection()['token']['ok'])

    def test_validates_each_credential(self):
        from plugins.installed.meta_commerce.services.graph import verify_connection

        _connect()
        me = MagicMock()
        me.json.return_value = {'id': '1'}
        me.raise_for_status.return_value = None
        cat = MagicMock()
        cat.json.return_value = {'name': 'My Catalog', 'product_count': 42}
        cat.raise_for_status.return_value = None
        acct = MagicMock()
        acct.json.return_value = {'name': 'Ad Acct', 'currency': 'USD'}
        acct.raise_for_status.return_value = None
        px = MagicMock()
        px.json.return_value = {'name': 'Pixel'}
        px.raise_for_status.return_value = None
        with patch('requests.get', side_effect=[me, cat, acct, px]):
            res = verify_connection()
        self.assertTrue(res['token']['ok'])
        self.assertIn('My Catalog', res['catalog']['detail'])
        self.assertIn('42', res['catalog']['detail'])
        self.assertTrue(res['ad_account']['ok'])
        self.assertTrue(res['pixel']['ok'])


class CatalogPushTests(_Iso, TestCase):
    def test_catalog_item_shape(self):
        item = {
            'id': 'SKU1',
            'title': 'Dune',
            'description': 'x',
            'link': 'https://x/p/',
            'image_link': 'https://x/i.jpg',
            'availability': 'in stock',
            'price': '9.00 USD',
            'condition': 'new',
            'brand': 'Penguin',
            'item_group_id': 'G1',
        }
        res = catalog_api._catalog_item(item)
        self.assertEqual(res['retailer_id'], 'SKU1')
        self.assertEqual(res['availability'], 'in_stock')  # Catalog API uses underscores
        self.assertEqual(res['item_group_id'], 'G1')

    def test_push_batches_when_connected(self):
        from decimal import Decimal

        from django.core.files.base import ContentFile
        from djmoney.money import Money

        from plugins.installed.catalog.models import Product, ProductImage

        _connect()
        gif = (
            b'GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!'
            b'\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;'
        )
        p = Product.objects.create(
            name='Dune',
            slug='dune',
            sku='SKU1',
            price=Money(Decimal('9'), 'USD'),
            product_type='simple',
            status='active',
        )
        ProductImage(product=p, is_primary=True).image.save('d.gif', ContentFile(gif), save=True)
        resp = MagicMock()
        resp.json.return_value = {'handles': ['h']}
        resp.raise_for_status.return_value = None
        with patch('requests.post', return_value=resp) as post:
            res = catalog_api.push_products()
        self.assertTrue(res['ok'])
        self.assertEqual(res['sent'], 1)
        # Hit the catalog items_batch endpoint with PRODUCT_ITEM requests.
        url = post.call_args.args[0]
        self.assertIn('555/items_batch', url)
        body = post.call_args.kwargs['data']
        self.assertEqual(body['item_type'], 'PRODUCT_ITEM')
        self.assertEqual(json.loads(body['requests'])[0]['method'], 'UPDATE')


class DiagnosticsTests(_Iso, TestCase):
    def test_not_connected(self):
        self.assertEqual(catalog_api.product_diagnostics()['reason'], 'not_connected')

    def test_summarises_review_status(self):
        _connect()
        resp = MagicMock()
        resp.json.return_value = {
            'data': [
                {'review_status': 'rejected', 'errors': [{'message': 'Missing images'}]},
                {'review_status': 'approved', 'errors': []},
            ],
            'paging': {},
        }
        resp.raise_for_status.return_value = None
        with patch('requests.get', return_value=resp):
            d = catalog_api.product_diagnostics()
        self.assertTrue(d['ok'])
        self.assertEqual(d['counts']['rejected'], 1)
        self.assertEqual(d['counts']['approved'], 1)
        self.assertEqual(d['issues'][0]['description'], 'Missing images')


class AdsTests(_Iso, TestCase):
    def test_report_parses_insights(self):
        _connect()
        resp = MagicMock()
        resp.json.return_value = {
            'data': [
                {
                    'campaign_id': '1',
                    'campaign_name': 'Sales',
                    'spend': '5',
                    'impressions': '1000',
                    'clicks': '40',
                    'actions': [{'action_type': 'purchase', 'value': '4'}],
                    'action_values': [{'action_type': 'purchase', 'value': '20'}],
                }
            ]
        }
        resp.raise_for_status.return_value = None
        with patch('requests.get', return_value=resp):
            rep = ads_api.campaign_report(days=30)
        self.assertTrue(rep['ok'])
        c = rep['campaigns'][0]
        self.assertEqual(c['spend'], 5.0)
        self.assertEqual(c['purchases'], 4.0)
        self.assertEqual(c['roas'], 4.0)  # 20 / 5

    def test_status_validates(self):
        _connect()
        self.assertEqual(ads_api.set_campaign_status('1', 'BOGUS')['reason'], 'bad_status')

    def test_non_numeric_campaign_id_rejected(self):
        # A crafted path can't redirect the Graph write to another endpoint.
        _connect()
        self.assertEqual(
            ads_api.set_campaign_status('../me/settings', 'PAUSED')['reason'], 'bad_campaign_id'
        )

    def test_error_redacts_access_token(self):
        from plugins.installed.meta_commerce.services.graph import _err

        class _E(Exception):
            response = None

        e = _E('GET https://graph.facebook.com/v21.0/x?access_token=SECRET123&y=1 failed 400')
        self.assertNotIn('SECRET123', _err(e))
        self.assertIn('REDACTED', _err(e))

    def test_create_campaign_posts_objective(self):
        _connect()
        resp = MagicMock()
        resp.json.return_value = {'id': 'c1'}
        resp.raise_for_status.return_value = None
        with patch('requests.post', return_value=resp) as post:
            res = ads_api.create_catalog_campaign(name='Sales', daily_budget=10)
        self.assertTrue(res['ok'])
        body = post.call_args.kwargs['data']
        self.assertEqual(body['objective'], 'OUTCOME_SALES')
        self.assertEqual(body['daily_budget'], '1000')  # $10 → 1000 cents
        self.assertEqual(body['status'], 'PAUSED')


class CapiTests(_Iso, TestCase):
    def test_purchase_posts_hashed_email_and_content_ids(self):
        _connect()
        order = MagicMock()
        order.total.amount = 25
        order.total.currency = 'USD'
        order.email = 'BUYER@example.com'
        order.order_number = 'A-100'
        line = MagicMock()
        line.sku = 'SKU1'
        line.quantity = 2
        order.items = [line]
        resp = MagicMock()
        resp.json.return_value = {'events_received': 1}
        resp.raise_for_status.return_value = None
        with patch('requests.post', return_value=resp) as post:
            res = capi.send_purchase(order)
        self.assertTrue(res['ok'])
        events = json.loads(post.call_args.kwargs['data']['data'])
        ev = events[0]
        self.assertEqual(ev['event_name'], 'Purchase')
        self.assertEqual(ev['custom_data']['content_ids'], ['SKU1'])
        self.assertEqual(ev['custom_data']['value'], 25.0)
        # Email is sha256-hashed, never raw.
        self.assertNotIn('BUYER@example.com', json.dumps(ev))
        self.assertEqual(len(ev['user_data']['em'][0]), 64)

    def test_add_to_cart_event(self):
        from decimal import Decimal

        from djmoney.money import Money

        _connect()
        product = MagicMock()
        product.sku = 'SKU1'
        product.price = Money(Decimal('9.00'), 'USD')
        resp = MagicMock()
        resp.json.return_value = {'events_received': 1}
        resp.raise_for_status.return_value = None
        with patch('requests.post', return_value=resp) as post:
            res = capi.send_add_to_cart(product=product, variant=None, quantity=2)
        self.assertTrue(res['ok'])
        ev = json.loads(post.call_args.kwargs['data']['data'])[0]
        self.assertEqual(ev['event_name'], 'AddToCart')
        self.assertEqual(ev['custom_data']['content_ids'], ['SKU1'])
        self.assertEqual(ev['custom_data']['value'], 18.0)  # 9 × 2

    def test_initiate_checkout_event(self):
        from decimal import Decimal

        from djmoney.money import Money

        _connect()
        cart = MagicMock()
        cart.total = Money(Decimal('30.00'), 'USD')
        line = MagicMock()
        line.sku = 'SKU1'
        line.quantity = 1
        cart.items = [line]
        resp = MagicMock()
        resp.json.return_value = {'events_received': 1}
        resp.raise_for_status.return_value = None
        with patch('requests.post', return_value=resp) as post:
            res = capi.send_initiate_checkout(cart)
        self.assertTrue(res['ok'])
        ev = json.loads(post.call_args.kwargs['data']['data'])[0]
        self.assertEqual(ev['event_name'], 'InitiateCheckout')
        self.assertEqual(ev['custom_data']['value'], 30.0)
