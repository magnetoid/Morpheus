"""TikTok Commerce — feed, pixel, events API, ads API, dashboard boundaries."""

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
from plugins.installed.tiktok_commerce.services import ads_api, events_api
from plugins.installed.tiktok_commerce.services.feed import build_feed
from plugins.installed.tiktok_commerce.services.mapping import map_product
from plugins.installed.tiktok_commerce.services.settings import tiktok_settings
from plugins.installed.tiktok_commerce.templatetags.tiktok_commerce import tiktok_pixel

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
                p = fn('tiktok_commerce')
            except Exception:  # noqa: BLE001
                p = None
            if p is not None:
                return p
    from plugins.installed.tiktok_commerce.app import TiktokCommercePlugin

    return TiktokCommercePlugin()


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
    def test_meta_value_format_and_xml(self):
        item = map_product(_product('dune', 'SKU1'), tiktok_settings())
        self.assertEqual(item['availability'], 'in stock')
        xml, stats = build_feed(log=False)
        self.assertEqual(stats['items'], 1)
        self.assertIsNotNone(ET.fromstring(xml).find(f'.//item/{_G}price'))

    def test_endpoint(self):
        _product('z', 'Z1')
        r = Client().get('/feeds/tiktok-catalog.xml')
        self.assertEqual(r.status_code, 200)
        self.assertIn('application/xml', r['Content-Type'])


class PixelTests(TestCase):
    def setUp(self):
        _plugin().invalidate_config_cache()

    def tearDown(self):
        _plugin().invalidate_config_cache()

    def _enable(self, code='ABCDEF123456'):
        p = _plugin()
        p.set_config('pixel_enabled', True)
        p.set_config('pixel_code', code)
        p.invalidate_config_cache()

    def test_disabled(self):
        self.assertEqual(tiktok_pixel(Context({'request': RequestFactory().get('/')})), '')

    def test_invalid_code(self):
        self._enable(code='bad code!')
        self.assertEqual(tiktok_pixel(Context({'request': RequestFactory().get('/')})), '')

    def test_enabled_emits_ttq(self):
        self._enable()
        html = tiktok_pixel(Context({'request': RequestFactory().get('/')}))
        self.assertIn('ttq', html)
        self.assertIn('"ABCDEF123456"', html)

    def test_purchase_dedup_on_confirmation(self):
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
        html = tiktok_pixel(ctx)
        self.assertIn('CompletePayment', html)
        self.assertIn('event_id:"A-1"', html.replace(' ', ''))

    def test_xss_safe_sku(self):
        self._enable()
        p = Product.objects.create(
            name='Bad',
            slug='bad',
            sku='</script><img onerror=x>',
            price=Money(Decimal('5'), 'USD'),
            product_type='simple',
            status='active',
        )
        html = tiktok_pixel(
            Context({'request': RequestFactory().get('/products/bad/'), 'product': p})
        )
        self.assertNotIn('</script><img', html)


class _Iso:
    def setUp(self):
        _plugin().invalidate_config_cache()

    def tearDown(self):
        _plugin().invalidate_config_cache()

    def _connect(self):
        p = _plugin()
        for k, v in {
            'access_token': 'TOK',
            'advertiser_id': '999',
            'catalog_id': '5',
            'pixel_code': 'ABCDEF123456',
        }.items():
            p.set_config(k, v)
        p.invalidate_config_cache()


class EventsTests(_Iso, TestCase):
    def test_not_connected(self):
        self.assertEqual(events_api.send_complete_payment(MagicMock())['reason'], 'not_connected')

    def test_complete_payment_hashes_email_and_resolves_manager(self):
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
        resp.json.return_value = {'code': 0, 'data': {}}
        resp.raise_for_status.return_value = None
        with patch('requests.post', return_value=resp) as post:
            res = events_api.send_complete_payment(order)
        self.assertTrue(res['ok'])
        body = post.call_args.kwargs['json']
        ev = body['data'][0]
        self.assertEqual(ev['event'], 'CompletePayment')
        self.assertEqual(ev['properties']['contents'][0]['content_id'], 'SKU1')
        self.assertNotIn('B@x.test', json.dumps(ev))
        self.assertEqual(len(ev['user']['email']), 64)


class AdsTests(_Iso, TestCase):
    def test_not_connected(self):
        self.assertEqual(ads_api.campaign_report()['reason'], 'not_connected')

    def test_report_parses(self):
        self._connect()
        resp = MagicMock()
        resp.json.return_value = {
            'code': 0,
            'data': {
                'list': [
                    {
                        'dimensions': {'campaign_id': '1'},
                        'metrics': {
                            'campaign_name': 'S',
                            'spend': '10',
                            'impressions': '100',
                            'clicks': '5',
                            'complete_payment': '3',
                        },
                    }
                ]
            },
        }
        resp.raise_for_status.return_value = None
        with patch('requests.get', return_value=resp):
            rep = ads_api.campaign_report(days=30)
        self.assertTrue(rep['ok'])
        self.assertEqual(rep['campaigns'][0]['spend'], 10.0)
        self.assertEqual(rep['campaigns'][0]['conversions'], 3.0)

    def test_status_and_id_validation(self):
        self._connect()
        self.assertEqual(ads_api.set_campaign_status('1', 'BOGUS')['reason'], 'bad_status')
        self.assertEqual(ads_api.set_campaign_status('../x', 'ENABLE')['reason'], 'bad_campaign_id')


class DiagnosticsTests(_Iso, TestCase):
    def test_not_connected(self):
        from plugins.installed.tiktok_commerce.services.diagnostics import catalog_diagnostics

        self.assertEqual(catalog_diagnostics()['reason'], 'not_connected')

    def test_defensive_parse_of_product_status(self):
        from plugins.installed.tiktok_commerce.services.diagnostics import catalog_diagnostics

        self._connect()
        resp = MagicMock()
        resp.json.return_value = {
            'code': 0,
            'data': {
                'products': [
                    {'status': 'REJECTED', 'reject_reason': ['Missing GTIN']},
                    {'status': 'APPROVED', 'reject_reason': []},
                    {'audit_status': 'pending_review'},
                ],
                'page_info': {'total_page': 1},
            },
        }
        resp.raise_for_status.return_value = None
        with patch('requests.get', return_value=resp):
            d = catalog_diagnostics()
        self.assertTrue(d['ok'])
        self.assertEqual(d['counts']['rejected'], 1)
        self.assertEqual(d['counts']['approved'], 1)
        self.assertEqual(d['counts']['pending'], 1)
        self.assertEqual(d['issues'][0]['description'], 'Missing GTIN')

    def test_unexpected_shape_degrades_gracefully(self):
        from plugins.installed.tiktok_commerce.services.diagnostics import catalog_diagnostics

        self._connect()
        resp = MagicMock()
        resp.json.return_value = {'code': 0, 'data': {'something_else': True}}
        resp.raise_for_status.return_value = None
        with patch('requests.get', return_value=resp):
            d = catalog_diagnostics()
        # No crash, no false data — just zero counts.
        self.assertTrue(d['ok'])
        self.assertEqual(d['counts']['total'], 0)
        self.assertEqual(d['issues'], [])


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
        self.assertEqual(Client().get('/dashboard/apps/tiktok_commerce/overview/').status_code, 302)
        r = self._staff().get('/dashboard/apps/tiktok_commerce/overview/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'tiktok-catalog.xml')
        r2 = self._staff().get('/dashboard/apps/tiktok_commerce/ads/')
        self.assertEqual(r2.status_code, 200)
        self.assertContains(r2, 'Connect TikTok Ads')
