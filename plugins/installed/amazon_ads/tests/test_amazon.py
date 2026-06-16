"""Amazon Ads — campaign management + async reporting (mocked HTTP) + dashboard."""

# ruff: noqa: PLC0415
from __future__ import annotations

import gzip
import io
import json
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from plugins.installed.amazon_ads.services import ads_api, reporting

User = get_user_model()


def _plugin():
    from plugins.registry import plugin_registry

    for attr in ('get', 'get_plugin'):
        fn = getattr(plugin_registry, attr, None)
        if callable(fn):
            try:
                p = fn('amazon_ads')
            except Exception:  # noqa: BLE001
                p = None
            if p is not None:
                return p
    from plugins.installed.amazon_ads.plugin import AmazonAdsPlugin

    return AmazonAdsPlugin()


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
            'profile_id': '999',
            'region': 'na',
        }.items():
            p.set_config(k, v)
        p.invalidate_config_cache()


class ConnectionTests(_Iso, TestCase):
    def test_not_connected(self):
        self.assertEqual(ads_api.list_campaigns()['reason'], 'not_connected')
        self.assertEqual(reporting.fetch_metrics()['reason'], 'not_connected')

    def test_region_base_url(self):
        from plugins.installed.amazon_ads.services.api import base_url

        self._connect()
        self.assertEqual(base_url(), 'https://advertising-api.amazon.com')
        _plugin().set_config('region', 'eu')
        _plugin().invalidate_config_cache()
        self.assertIn('-eu', base_url())


class CampaignTests(_Iso, TestCase):
    def test_list_campaigns_parses(self):
        self._connect()
        token = MagicMock()
        token.json.return_value = {'access_token': 'T'}
        token.raise_for_status.return_value = None
        camps = MagicMock()
        camps.content = b'{"campaigns":[{"campaignId":111,"name":"SP","state":"ENABLED","budget":{"budget":20}}]}'
        camps.json.return_value = {
            'campaigns': [
                {'campaignId': 111, 'name': 'SP', 'state': 'ENABLED', 'budget': {'budget': 20}}
            ]
        }
        camps.raise_for_status.return_value = None
        with (
            patch('requests.post', return_value=token),
            patch('requests.request', return_value=camps) as req,
        ):
            rep = ads_api.list_campaigns()
        self.assertTrue(rep['ok'])
        c = rep['campaigns'][0]
        self.assertEqual(c['id'], '111')
        self.assertEqual(c['name'], 'SP')
        self.assertEqual(c['budget'], 20)
        # Hit the v3 list endpoint with the auth header (Scope = profile).
        self.assertIn('/sp/campaigns/list', req.call_args.args[1])
        self.assertEqual(req.call_args.kwargs['headers']['Amazon-Advertising-API-Scope'], '999')

    def test_status_and_id_validation(self):
        self._connect()
        self.assertEqual(ads_api.set_campaign_status('1', 'BOGUS')['reason'], 'bad_status')
        self.assertEqual(
            ads_api.set_campaign_status('../x', 'ENABLED')['reason'], 'bad_campaign_id'
        )


class ReportingTests(_Iso, TestCase):
    def test_gzip_json_parse_keyed_by_campaign(self):
        rows = [
            {
                'campaignId': 111,
                'cost': '12.5',
                'clicks': 40,
                'impressions': 1000,
                'purchases7d': 4,
                'sales7d': '99',
            }
        ]
        gz = io.BytesIO()
        with gzip.GzipFile(fileobj=gz, mode='wb') as f:
            f.write(json.dumps(rows).encode())
        resp = MagicMock()
        resp.content = gz.getvalue()
        resp.raise_for_status.return_value = None
        with patch('requests.get', return_value=resp):
            out = reporting._download_and_parse('https://x/report')
        self.assertEqual(out['111']['cost'], 12.5)
        self.assertEqual(out['111']['sales'], 99.0)
        self.assertEqual(out['111']['purchases'], 4.0)

    def test_fetch_fail_soft_on_submit(self):
        self._connect()
        token = MagicMock()
        token.json.return_value = {'access_token': 'T'}
        token.raise_for_status.return_value = None
        err = MagicMock()
        err.content = b'{"message":"bad"}'
        err.json.return_value = {'message': 'bad'}
        err.raise_for_status.side_effect = Exception('400')
        with (
            patch('requests.post', return_value=token),
            patch('requests.request', return_value=err),
        ):
            res = reporting.fetch_metrics(days=30)
        self.assertFalse(res['ok'])
        self.assertEqual(res['reason'], 'submit_failed')


class DashboardTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username='s', email='s@x.test', password='pw', is_staff=True
        )

    def test_boundary_and_render(self):
        self.assertEqual(Client().get('/dashboard/apps/amazon_ads/ads/').status_code, 302)
        c = Client()
        c.force_login(self.staff)
        r = c.get('/dashboard/apps/amazon_ads/ads/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Connect Amazon Ads')
