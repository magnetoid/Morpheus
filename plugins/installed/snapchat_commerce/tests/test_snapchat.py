"""Snapchat Commerce — feed, pixel, Conversions API, ads API, dashboard boundaries."""

# ruff: noqa: PLC0415
from __future__ import annotations

import json
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.template import Context
from django.test import Client, RequestFactory, TestCase
from djmoney.money import Money

from plugins.installed.catalog.models import Product, ProductImage
from plugins.installed.snapchat_commerce.services import ads_api, capi
from plugins.installed.snapchat_commerce.services.feed import build_feed
from plugins.installed.snapchat_commerce.services.mapping import map_product
from plugins.installed.snapchat_commerce.services.settings import snapchat_settings
from plugins.installed.snapchat_commerce.templatetags.snapchat_commerce import snap_pixel

User = get_user_model()
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
                p = fn('snapchat_commerce')
            except Exception:  # noqa: BLE001
                p = None
            if p is not None:
                return p
    from plugins.installed.snapchat_commerce.app import SnapchatCommercePlugin

    return SnapchatCommercePlugin()


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


class _Mgr:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class FeedTests(TestCase):
    def test_meta_value_format_and_xml(self):
        item = map_product(_product('dune', 'SKU1'), snapchat_settings())
        self.assertEqual(item['availability'], 'in stock')
        xml, stats = build_feed(log=False)
        self.assertEqual(stats['items'], 1)
        self.assertIn('SKU1', xml)


class PixelTests(TestCase):
    def _enable(self, pixel_id='abc-123-def-456'):
        p = _plugin()
        p.set_config('pixel_enabled', True)
        p.set_config('pixel_id', pixel_id)
        p.invalidate_config_cache()

    def test_disabled(self):
        self.assertEqual(snap_pixel(Context({'request': RequestFactory().get('/')})), '')

    def test_invalid_id(self):
        self._enable(pixel_id='bad id!')
        self.assertEqual(snap_pixel(Context({'request': RequestFactory().get('/')})), '')

    def test_enabled_emits_snaptr(self):
        self._enable()
        html = snap_pixel(Context({'request': RequestFactory().get('/')}))
        self.assertIn('snaptr', html)
        self.assertIn('"abc-123-def-456"', html)
        self.assertIn('PAGE_VIEW', html)

    def test_purchase_dedup_on_confirmation(self):
        self._enable()
        line = type('L', (), {'sku': 'SKU1', 'quantity': 1})()
        order = type(
            'O',
            (),
            {'order_number': 'A-1', 'total': Money(Decimal('25'), 'USD'), 'items': _Mgr([line])},
        )()
        ctx = Context({'request': RequestFactory().get('/order/confirmation/A-1/'), 'order': order})
        html = snap_pixel(ctx)
        self.assertIn('PURCHASE', html)
        self.assertIn('transaction_id', html)
        self.assertIn('A-1', html)

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
        html = snap_pixel(
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
            'client_id': 'CID',
            'client_secret': 'SEC',
            'refresh_token': 'RT',
            'ad_account_id': 'acct-123-456',
            'pixel_id': 'pix-123-456',
        }.items():
            p.set_config(k, v)
        p.invalidate_config_cache()


class CapiTests(_Iso, TestCase):
    def test_not_connected(self):
        self.assertEqual(capi.send_purchase(MagicMock())['reason'], 'not_connected')

    def test_purchase_hashes_email_and_resolves_manager(self):
        self._connect()
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
        resp.json.return_value = {'status': 'SUCCESS'}
        resp.raise_for_status.return_value = None
        with (
            patch(
                'plugins.installed.snapchat_commerce.services.capi.access_token', return_value='TOK'
            ),
            patch('requests.post', return_value=resp) as post,
        ):
            res = capi.send_purchase(order)
        self.assertTrue(res['ok'])
        ev = post.call_args.kwargs['json']['data'][0]
        self.assertEqual(ev['event_name'], 'PURCHASE')
        self.assertEqual(ev['event_id'], 'A-1')
        self.assertIn('SKU1', ev['custom_data']['content_ids'])
        self.assertNotIn('B@x.test', json.dumps(ev))
        self.assertEqual(len(ev['user_data']['em'][0]), 64)


class AdsTests(_Iso, TestCase):
    def test_not_connected(self):
        self.assertEqual(ads_api.campaign_report()['reason'], 'not_connected')

    def test_report_parses_nested_stats(self):
        self._connect()
        resp = MagicMock()
        resp.json.return_value = {
            'total_stats': [
                {
                    'total_stat': {
                        'breakdown_stats': {
                            'campaign': [
                                {
                                    'id': 'c-1',
                                    'stats': {
                                        'spend': 10_000_000,
                                        'impressions': 100,
                                        'swipes': 5,
                                        'conversion_purchases': 3,
                                    },
                                }
                            ]
                        }
                    }
                }
            ]
        }
        resp.raise_for_status.return_value = None
        with (
            patch(
                'plugins.installed.snapchat_commerce.services.api.access_token', return_value='TOK'
            ),
            patch('requests.request', return_value=resp),
        ):
            rep = ads_api.campaign_report(days=30)
        self.assertTrue(rep['ok'])
        self.assertEqual(rep['campaigns'][0]['spend'], 10.0)
        self.assertEqual(rep['campaigns'][0]['conversions'], 3.0)

    def test_status_and_id_validation(self):
        self._connect()
        self.assertEqual(ads_api.set_campaign_status('c-1', 'BOGUS')['reason'], 'bad_status')
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
            Client().get('/dashboard/apps/snapchat_commerce/overview/').status_code, 302
        )
        r = self._staff().get('/dashboard/apps/snapchat_commerce/overview/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'snapchat-catalog.xml')
        r2 = self._staff().get('/dashboard/apps/snapchat_commerce/ads/')
        self.assertEqual(r2.status_code, 200)
        self.assertContains(r2, 'Connect Snapchat Ads')
