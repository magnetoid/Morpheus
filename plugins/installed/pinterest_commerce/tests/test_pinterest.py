"""Pinterest Commerce — feed, tag, Conversions API, Ads API, dashboard."""

# ruff: noqa: PLC0415
from __future__ import annotations

import json
from decimal import Decimal
from unittest.mock import MagicMock, patch
from xml.etree import ElementTree as ET

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.template import Context
from django.test import Client, RequestFactory, TestCase
from djmoney.money import Money

from plugins.installed.catalog.models import Product, ProductImage
from plugins.installed.pinterest_commerce.services import ads_api, capi
from plugins.installed.pinterest_commerce.services.feed import build_feed
from plugins.installed.pinterest_commerce.services.mapping import map_product
from plugins.installed.pinterest_commerce.services.settings import pinterest_settings
from plugins.installed.pinterest_commerce.templatetags.pinterest_commerce import pinterest_tag

User = get_user_model()
_G = '{http://base.google.com/ns/1.0}'
_GIF = (
    b'GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!'
    b'\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;'
)


def _plugin():
    from plugins.registry import app_registry

    for attr in ('get', 'get_plugin'):
        fn = getattr(app_registry, attr, None)
        if callable(fn):
            try:
                p = fn('pinterest_commerce')
            except Exception:  # noqa: BLE001
                p = None
            if p is not None:
                return p
    from plugins.installed.pinterest_commerce.app import PinterestCommercePlugin

    return PinterestCommercePlugin()


def _product(slug, sku, *, image=True):
    p = Product.objects.create(
        name=slug.title(),
        slug=slug,
        sku=sku,
        price=Money(Decimal('9.00'), 'USD'),
        product_type='simple',
        status='active',
    )
    if image:
        ProductImage(product=p, is_primary=True).image.save(
            f'{slug}.gif', ContentFile(_GIF), save=True
        )
    return p


class FeedTests(TestCase):
    def test_format_and_endpoint(self):
        item = map_product(_product('dune', 'SKU1'), pinterest_settings())
        self.assertEqual(item['availability'], 'in stock')
        xml, stats = build_feed(log=False)
        self.assertEqual(stats['items'], 1)
        self.assertIsNotNone(ET.fromstring(xml).find(f'.//item/{_G}price'))
        r = Client().get('/feeds/pinterest-catalog.xml')
        self.assertEqual(r.status_code, 200)


class TagTests(TestCase):
    def setUp(self):
        _plugin().invalidate_config_cache()

    def tearDown(self):
        _plugin().invalidate_config_cache()

    def _enable(self, tag_id='2613000000000'):
        p = _plugin()
        p.set_config('tag_enabled', True)
        p.set_config('tag_id', tag_id)
        p.invalidate_config_cache()

    def test_disabled(self):
        self.assertEqual(pinterest_tag(Context({'request': RequestFactory().get('/')})), '')

    def test_invalid_tag_id(self):
        self._enable(tag_id='not-numeric')
        self.assertEqual(pinterest_tag(Context({'request': RequestFactory().get('/')})), '')

    def test_enabled_emits_pintrk(self):
        self._enable()
        html = pinterest_tag(Context({'request': RequestFactory().get('/')}))
        self.assertIn('pintrk', html)
        self.assertIn('"2613000000000"', html)

    def test_checkout_dedup_on_confirmation(self):
        self._enable()

        class _Mgr:
            def __init__(self, rows):
                self._rows = rows

            def all(self):
                return self._rows

        line = type('L', (), {'sku': 'SKU1', 'quantity': 1})()
        order = type(
            'O',
            (),
            {'order_number': 'A-1', 'total': Money(Decimal('25'), 'USD'), 'items': _Mgr([line])},
        )()
        ctx = Context({'request': RequestFactory().get('/order/confirmation/A-1/'), 'order': order})
        html = pinterest_tag(ctx)
        self.assertIn('"track","checkout"', html.replace(' ', ''))
        self.assertIn('event_id:"A-1"', html.replace(' ', ''))


class _Iso:
    def setUp(self):
        _plugin().invalidate_config_cache()

    def tearDown(self):
        _plugin().invalidate_config_cache()

    def _connect(self):
        p = _plugin()
        for k, v in {
            'access_token': 'TOK',
            'ad_account_id': '549',
            'tag_id': '2613000000000',
        }.items():
            p.set_config(k, v)
        p.invalidate_config_cache()


class CapiTests(_Iso, TestCase):
    def test_not_connected(self):
        self.assertEqual(capi.send_checkout(MagicMock())['reason'], 'not_connected')

    def test_checkout_hashes_email_and_resolves_manager(self):
        self._connect()

        class _Mgr:
            def __init__(self, rows):
                self._rows = rows

            def all(self):
                return self._rows

        line = type('L', (), {'sku': 'SKU1', 'quantity': 2})()
        order = type(
            'O',
            (),
            {
                'order_number': 'A-1',
                'total': Money(Decimal('25'), 'USD'),
                'email': 'B@x.test',
                'items': _Mgr([line]),
            },
        )()
        resp = MagicMock()
        resp.json.return_value = {'num_events_received': 1}
        resp.raise_for_status.return_value = None
        with patch('requests.post', return_value=resp) as post:
            res = capi.send_checkout(order)
        self.assertTrue(res['ok'])
        ev = post.call_args.kwargs['json']['data'][0]
        self.assertEqual(ev['event_name'], 'checkout')
        self.assertEqual(ev['custom_data']['content_ids'], ['SKU1'])
        self.assertNotIn('B@x.test', json.dumps(ev))
        self.assertEqual(len(ev['user_data']['em'][0]), 64)
        # URL hits the ad account events endpoint.
        self.assertIn('ad_accounts/549/events', post.call_args.args[0])


class DiagnosticsTests(_Iso, TestCase):
    def test_not_connected(self):
        from plugins.installed.pinterest_commerce.services.diagnostics import feed_diagnostics

        # No catalog_feed_id set → not_connected.
        self.assertEqual(feed_diagnostics()['reason'], 'not_connected')

    def test_parses_processing_results(self):
        from plugins.installed.pinterest_commerce.services.diagnostics import feed_diagnostics

        p = _plugin()
        for k, v in {'access_token': 'TOK', 'catalog_feed_id': '777'}.items():
            p.set_config(k, v)
        p.invalidate_config_cache()
        resp = MagicMock()
        resp.json.return_value = {
            'items': [
                {
                    'status': 'COMPLETED',
                    'product_counts': {'original': 1064, 'ingested': 1060},
                    'validation_details': {
                        'errors': {'IMAGE_LINK_INVALID': {'message': 'Bad image', 'count': 4}}
                    },
                }
            ]
        }
        resp.raise_for_status.return_value = None
        with patch('requests.get', return_value=resp):
            d = feed_diagnostics()
        self.assertTrue(d['ok'])
        self.assertEqual(d['counts']['ingested'], 1060)
        self.assertEqual(d['issues'][0]['description'], 'Bad image')
        self.assertEqual(d['issues'][0]['count'], 4)


class AdsTests(_Iso, TestCase):
    def test_not_connected(self):
        self.assertEqual(ads_api.campaign_report()['reason'], 'not_connected')

    def test_report_lists_then_analytics(self):
        self._connect()
        list_resp = MagicMock()
        list_resp.json.return_value = {'items': [{'id': '1', 'name': 'Sales'}]}
        list_resp.raise_for_status.return_value = None
        analytics_resp = MagicMock()
        analytics_resp.json.return_value = [
            {
                'campaign_id': '1',
                'metrics': {
                    'SPEND_IN_DOLLAR': '10',
                    'IMPRESSION_1': '100',
                    'CLICKTHROUGH_1': '5',
                    'TOTAL_CHECKOUT': '3',
                },
            }
        ]
        analytics_resp.raise_for_status.return_value = None
        with patch('requests.get', side_effect=[list_resp, analytics_resp]):
            rep = ads_api.campaign_report(days=30)
        self.assertTrue(rep['ok'])
        self.assertEqual(rep['campaigns'][0]['name'], 'Sales')
        self.assertEqual(rep['campaigns'][0]['spend'], 10.0)
        self.assertEqual(rep['campaigns'][0]['conversions'], 3.0)

    def test_status_and_id_validation(self):
        self._connect()
        self.assertEqual(ads_api.set_campaign_status('1', 'BOGUS')['reason'], 'bad_status')
        self.assertEqual(ads_api.set_campaign_status('../x', 'ACTIVE')['reason'], 'bad_campaign_id')


class DashboardTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username='s', email='s@x.test', password='pw', is_staff=True
        )

    def _staff(self):
        c = Client()
        c.force_login(self.staff)
        return c

    def test_boundaries_and_render(self):
        self.assertEqual(
            Client().get('/dashboard/apps/pinterest_commerce/overview/').status_code, 302
        )
        r = self._staff().get('/dashboard/apps/pinterest_commerce/overview/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'pinterest-catalog.xml')
        r2 = self._staff().get('/dashboard/apps/pinterest_commerce/ads/')
        self.assertEqual(r2.status_code, 200)
        self.assertContains(r2, 'Connect Pinterest Ads')
