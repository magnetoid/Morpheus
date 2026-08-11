"""Content API + Ads API + OAuth — graceful no-op when unconfigured, correct
request shaping when connected (HTTP mocked)."""

# ruff: noqa: PLC0415
from __future__ import annotations

from unittest.mock import MagicMock, patch

from django.core.cache import cache
from django.test import TestCase

from plugins.installed.google_shopping.services import ads_api, content_api, google_auth


def _gs_plugin():
    from plugins.registry import app_registry

    for attr in ('get', 'get_plugin'):
        fn = getattr(app_registry, attr, None)
        if callable(fn):
            try:
                p = fn('google_shopping')
            except Exception:  # noqa: BLE001
                p = None
            if p is not None:
                return p
    from plugins.installed.google_shopping.app import GoogleShoppingPlugin

    return GoogleShoppingPlugin()


def _connect(**extra):
    p = _gs_plugin()
    cfg = {
        'oauth_client_id': 'cid',
        'oauth_client_secret': 'secret',
        'oauth_refresh_token': 'refresh',
        'merchant_id': '123456',
        'ads_developer_token': 'devtok',
        'ads_customer_id': '111-222-3333',
        **extra,
    }
    for k, v in cfg.items():
        p.set_config(k, v)
    p.invalidate_config_cache()


class _Isolation:
    def setUp(self):
        cache.clear()
        _gs_plugin().invalidate_config_cache()

    def tearDown(self):
        cache.clear()
        _gs_plugin().invalidate_config_cache()


class NotConnectedTests(_Isolation, TestCase):
    def test_oauth_not_connected(self):
        self.assertFalse(google_auth.is_connected())
        self.assertIsNone(google_auth.access_token())

    def test_content_push_noops(self):
        res = content_api.push_products()
        self.assertFalse(res['ok'])
        self.assertEqual(res['reason'], 'not_connected')

    def test_ads_report_noops(self):
        self.assertFalse(ads_api.ads_connected())
        rep = ads_api.campaign_report()
        self.assertFalse(rep['ok'])
        self.assertEqual(rep['reason'], 'not_connected')


class OAuthTests(_Isolation, TestCase):
    def test_access_token_fetched_and_cached(self):
        _connect()
        resp = MagicMock()
        resp.json.return_value = {'access_token': 'ya29.TOKEN', 'expires_in': 3600}
        resp.raise_for_status.return_value = None
        with patch('requests.post', return_value=resp) as post:
            self.assertEqual(google_auth.access_token(), 'ya29.TOKEN')
            # Second call is served from cache — no second HTTP request.
            self.assertEqual(google_auth.access_token(), 'ya29.TOKEN')
            self.assertEqual(post.call_count, 1)


class OAuthConnectFlowTests(_Isolation, TestCase):
    def test_no_authorize_url_without_client(self):
        self.assertIsNone(google_auth.authorize_url('https://x/cb/'))

    def test_authorize_url_has_offline_consent_and_scopes(self):
        p = _gs_plugin()
        p.set_config('oauth_client_id', 'cid')
        p.set_config('oauth_client_secret', 'sec')
        p.invalidate_config_cache()
        url = google_auth.authorize_url('https://x/cb/')
        self.assertIn('access_type=offline', url)
        self.assertIn('prompt=consent', url)
        self.assertIn('auth%2Fcontent', url)  # content scope
        self.assertIn('auth%2Fadwords', url)  # ads scope

    def test_exchange_code_persists_refresh_token(self):
        p = _gs_plugin()
        p.set_config('oauth_client_id', 'cid')
        p.set_config('oauth_client_secret', 'sec')
        p.invalidate_config_cache()
        resp = MagicMock()
        resp.json.return_value = {'refresh_token': 'R3FRESH', 'access_token': 'A'}
        resp.raise_for_status.return_value = None
        with patch('requests.post', return_value=resp):
            res = google_auth.exchange_code('authcode', 'https://x/cb/')
        self.assertTrue(res['ok'])
        # Now fully connected — the refresh token was stored.
        self.assertTrue(google_auth.is_connected())

    def test_exchange_code_without_refresh_token_fails(self):
        p = _gs_plugin()
        p.set_config('oauth_client_id', 'cid')
        p.set_config('oauth_client_secret', 'sec')
        p.invalidate_config_cache()
        resp = MagicMock()
        resp.json.return_value = {'access_token': 'A'}  # no refresh_token
        resp.raise_for_status.return_value = None
        with patch('requests.post', return_value=resp):
            res = google_auth.exchange_code('authcode', 'https://x/cb/')
        self.assertFalse(res['ok'])
        self.assertEqual(res['reason'], 'no_refresh_token')


class ContentApiTests(_Isolation, TestCase):
    def test_content_product_shape(self):
        item = {
            'id': 'SKU1',
            'title': 'Dune',
            'description': 'A novel',
            'link': 'https://x/p/dune/',
            'image_link': 'https://x/i.jpg',
            'availability': 'in_stock',
            'price': '9.00 USD',
            'sale_price': '6.00 USD',
            'condition': 'new',
            'brand': 'Penguin',
            'identifier_exists': 'no',
        }
        from plugins.installed.google_shopping.services.settings import feed_settings

        res = content_api._content_product(item, feed_settings())
        self.assertEqual(res['offerId'], 'SKU1')
        self.assertEqual(res['price'], {'value': '9.00', 'currency': 'USD'})
        self.assertEqual(res['salePrice'], {'value': '6.00', 'currency': 'USD'})
        self.assertEqual(res['availability'], 'in stock')
        self.assertEqual(res['brand'], 'Penguin')
        self.assertFalse(res['identifierExists'])

    def test_push_sends_batch_when_connected(self):
        from decimal import Decimal

        from djmoney.money import Money

        from plugins.installed.catalog.models import Product, ProductImage

        _connect()
        gif = (
            b'GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!'
            b'\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;'
        )
        from django.core.files.base import ContentFile

        p = Product.objects.create(
            name='Dune',
            slug='dune',
            sku='SKU1',
            price=Money(Decimal('9.00'), 'USD'),
            product_type='simple',
            status='active',
        )
        ProductImage(product=p, is_primary=True).image.save('d.gif', ContentFile(gif), save=True)

        token_resp = MagicMock()
        token_resp.json.return_value = {'access_token': 'T'}
        token_resp.raise_for_status.return_value = None
        batch_resp = MagicMock()
        batch_resp.json.return_value = {'entries': [{'batchId': 1, 'product': {}}]}
        batch_resp.raise_for_status.return_value = None
        with patch('requests.post', side_effect=[token_resp, batch_resp]) as post:
            res = content_api.push_products()
        self.assertTrue(res['ok'])
        self.assertEqual(res['sent'], 1)
        # Last call hit the Content API batch endpoint with our merchant id.
        self.assertIn('123456/products/batch', post.call_args_list[-1].args[0])


class AdsApiTests(_Isolation, TestCase):
    def test_campaign_report_parses_metrics(self):
        _connect()
        token_resp = MagicMock()
        token_resp.json.return_value = {'access_token': 'T'}
        token_resp.raise_for_status.return_value = None
        search_resp = MagicMock()
        search_resp.json.return_value = [
            {
                'results': [
                    {
                        'campaign': {
                            'id': '1',
                            'name': 'Shopping',
                            'status': 'ENABLED',
                            'advertisingChannelType': 'SHOPPING',
                        },
                        'metrics': {
                            'costMicros': '5000000',
                            'clicks': '40',
                            'impressions': '1000',
                            'conversions': '4',
                            'conversionsValue': '20',
                        },
                    }
                ]
            }
        ]
        search_resp.raise_for_status.return_value = None
        with patch('requests.post', side_effect=[token_resp, search_resp]):
            rep = ads_api.campaign_report(days=30)
        self.assertTrue(rep['ok'])
        c = rep['campaigns'][0]
        self.assertEqual(c['cost'], 5.0)
        self.assertEqual(c['roas'], 4.0)  # value 20 / cost 5
        self.assertEqual(rep['totals']['conversions'], 4.0)

    def test_set_status_validates(self):
        _connect()
        self.assertEqual(ads_api.set_campaign_status('1', 'BOGUS')['reason'], 'bad_status')

    def test_create_shopping_campaign_two_mutates(self):
        _connect()
        token_resp = MagicMock()
        token_resp.json.return_value = {'access_token': 'T'}
        token_resp.raise_for_status.return_value = None
        budget_resp = MagicMock()
        budget_resp.json.return_value = {
            'results': [{'resourceName': 'customers/111/campaignBudgets/9'}]
        }
        budget_resp.raise_for_status.return_value = None
        camp_resp = MagicMock()
        camp_resp.json.return_value = {'results': [{'resourceName': 'customers/111/campaigns/8'}]}
        camp_resp.raise_for_status.return_value = None
        with patch('requests.post', side_effect=[token_resp, budget_resp, camp_resp]) as post:
            res = ads_api.create_shopping_campaign(
                name='Shopping', daily_budget=10, merchant_id='123456'
            )
        self.assertTrue(res['ok'])
        self.assertEqual(res['campaign'], 'customers/111/campaigns/8')
        # The budget mutate carries the micros amount (10 → 10_000_000).
        budget_call = post.call_args_list[1]
        self.assertEqual(
            budget_call.kwargs['json']['operations'][0]['create']['amountMicros'], '10000000'
        )

    def test_create_requires_name_and_merchant(self):
        _connect()
        self.assertEqual(
            ads_api.create_shopping_campaign(name='', daily_budget=10, merchant_id='1')['reason'],
            'missing_name_or_merchant',
        )


class DiagnosticsTests(_Isolation, TestCase):
    def test_not_connected(self):
        self.assertEqual(content_api.product_statuses()['reason'], 'not_connected')

    def test_summarises_issues(self):
        _connect()
        token_resp = MagicMock()
        token_resp.json.return_value = {'access_token': 'T'}
        token_resp.raise_for_status.return_value = None
        status_resp = MagicMock()
        status_resp.json.return_value = {
            'resources': [
                {
                    'destinationStatuses': [{'status': 'disapproved'}],
                    'itemLevelIssues': [
                        {'description': 'Missing GTIN', 'servability': 'disapproved'}
                    ],
                },
                {
                    'destinationStatuses': [{'status': 'active'}],
                    'itemLevelIssues': [],
                },
            ]
        }
        status_resp.raise_for_status.return_value = None
        with (
            patch('requests.get', return_value=status_resp),
            patch('requests.post', return_value=token_resp),
        ):
            d = content_api.product_statuses()
        self.assertTrue(d['ok'])
        self.assertEqual(d['counts']['disapproved'], 1)
        self.assertEqual(d['counts']['active'], 1)
        self.assertEqual(d['issues'][0]['description'], 'Missing GTIN')
        self.assertEqual(d['issues'][0]['count'], 1)
