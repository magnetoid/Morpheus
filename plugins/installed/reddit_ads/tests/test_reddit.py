"""Reddit Ads — pixel, Conversions API, Ads API, dashboard."""

# ruff: noqa: PLC0415
from __future__ import annotations

import json
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.template import Context
from django.test import Client, RequestFactory, TestCase
from djmoney.money import Money

from plugins.installed.reddit_ads.services import ads_api, capi
from plugins.installed.reddit_ads.templatetags.reddit_ads import reddit_pixel

User = get_user_model()


def _plugin():
    from plugins.registry import app_registry

    for attr in ('get', 'get_plugin'):
        fn = getattr(app_registry, attr, None)
        if callable(fn):
            try:
                p = fn('reddit_ads')
            except Exception:  # noqa: BLE001
                p = None
            if p is not None:
                return p
    from plugins.installed.reddit_ads.app import RedditAdsPlugin

    return RedditAdsPlugin()


class _Iso:
    def setUp(self):
        from django.core.cache import cache

        cache.clear()
        _plugin().invalidate_config_cache()

    def tearDown(self):
        from django.core.cache import cache

        cache.clear()
        _plugin().invalidate_config_cache()

    def _connect(self):
        p = _plugin()
        for k, v in {
            'client_id': 'cid',
            'client_secret': 'sec',
            'refresh_token': 'ref',
            'account_id': 'a2_acct',
            'pixel_id': 't2_pixel',
            'pixel_enabled': True,
        }.items():
            p.set_config(k, v)
        p.invalidate_config_cache()


class PixelTests(_Iso, TestCase):
    def test_disabled(self):
        self.assertEqual(reddit_pixel(Context({'request': RequestFactory().get('/')})), '')

    def test_enabled_emits_rdt(self):
        self._connect()
        html = reddit_pixel(Context({'request': RequestFactory().get('/')}))
        self.assertIn('redditstatic.com/ads/pixel.js', html)
        self.assertIn('"t2_pixel"', html)
        self.assertIn('PageVisit', html)

    def test_purchase_dedup_on_confirmation(self):
        self._connect()
        order = type('O', (), {'order_number': 'A-1', 'total': Money(Decimal('25'), 'USD')})()
        ctx = Context({'request': RequestFactory().get('/order/confirmation/A-1/'), 'order': order})
        html = reddit_pixel(ctx)
        self.assertIn('"track","Purchase"', html.replace(' ', ''))
        self.assertIn('"conversionId": "A-1"', html)

    def test_xss_safe_pixel_id(self):
        p = _plugin()
        p.set_config('pixel_enabled', True)
        p.set_config('pixel_id', '"/></script><script>alert(1)</script>')
        p.invalidate_config_cache()
        self.assertEqual(reddit_pixel(Context({'request': RequestFactory().get('/')})), '')


class CapiTests(_Iso, TestCase):
    def test_not_connected(self):
        self.assertEqual(capi.send_purchase(MagicMock())['reason'], 'not_connected')

    def test_purchase_hashes_email_and_dedup_id(self):
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
        token = MagicMock()
        token.json.return_value = {'access_token': 'T'}
        token.raise_for_status.return_value = None
        ok = MagicMock()
        ok.content = b'{}'
        ok.json.return_value = {}
        ok.raise_for_status.return_value = None
        with (
            patch('requests.post', return_value=token),
            patch('requests.request', return_value=ok) as req,
        ):
            res = capi.send_purchase(order)
        self.assertTrue(res['ok'])
        ev = req.call_args.kwargs['json']['events'][0]
        self.assertEqual(ev['event_type']['tracking_type'], 'Purchase')
        self.assertEqual(ev['event_metadata']['conversion_id'], 'A-1')
        self.assertEqual(ev['event_metadata']['products'], [{'id': 'SKU1'}])
        self.assertNotIn('B@x.test', json.dumps(ev))
        self.assertEqual(len(ev['user']['email']), 64)


class AdsTests(_Iso, TestCase):
    def test_not_connected(self):
        self.assertEqual(ads_api.list_campaigns()['reason'], 'not_connected')

    def test_list_and_report_parse(self):
        self._connect()
        token = MagicMock()
        token.json.return_value = {'access_token': 'T'}
        token.raise_for_status.return_value = None
        camps = MagicMock()
        camps.content = b'{"data":[]}'
        camps.json.return_value = {
            'data': [
                {
                    'id': 'c_1',
                    'name': 'Books',
                    'configured_status': 'ACTIVE',
                    'objective': 'CONVERSIONS',
                }
            ]
        }
        camps.raise_for_status.return_value = None
        with (
            patch('requests.post', return_value=token),
            patch('requests.request', return_value=camps),
        ):
            rep = ads_api.list_campaigns()
        self.assertTrue(rep['ok'])
        self.assertEqual(rep['campaigns'][0]['id'], 'c_1')
        self.assertEqual(rep['campaigns'][0]['status'], 'ACTIVE')

    def test_status_and_id_validation(self):
        self._connect()
        self.assertEqual(ads_api.set_campaign_status('c_1', 'BOGUS')['reason'], 'bad_status')
        self.assertEqual(
            ads_api.set_campaign_status('bad id!', 'ACTIVE')['reason'], 'bad_campaign_id'
        )


class BookCommunitiesTests(TestCase):
    def test_flat_list_dedups(self):
        from plugins.installed.reddit_ads.services.book_communities import all_communities

        subs = all_communities()
        self.assertIn('books', subs)
        self.assertIn('RomanceBooks', subs)
        self.assertEqual(len(subs), len(set(subs)))  # de-duplicated

    def test_genre_match_and_fallback(self):
        from plugins.installed.reddit_ads.services.book_communities import communities_for

        self.assertIn('RomanceBooks', communities_for('romance'))
        self.assertIn('printSF', communities_for('Sci-fi'))
        # Unknown genre → general readers.
        self.assertIn('books', communities_for('cookbooks-zzz'))


class DashboardTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username='s', email='s@x.test', password='pw', is_staff=True
        )

    def test_boundary_and_render(self):
        self.assertEqual(Client().get('/dashboard/apps/reddit_ads/ads/').status_code, 302)
        c = Client()
        c.force_login(self.staff)
        r = c.get('/dashboard/apps/reddit_ads/ads/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Connect Reddit Ads')
        self.assertContains(r, 'r/books')  # book-community targeting guide
