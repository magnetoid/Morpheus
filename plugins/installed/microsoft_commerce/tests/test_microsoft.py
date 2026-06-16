"""Microsoft / Bing Commerce — feed, UET tag, dashboard."""

# ruff: noqa: PLC0415
from __future__ import annotations

from decimal import Decimal
from xml.etree import ElementTree as ET

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.template import Context
from django.test import Client, RequestFactory, TestCase
from djmoney.money import Money

from plugins.installed.catalog.models import Product, ProductImage
from plugins.installed.microsoft_commerce.services.feed import build_feed
from plugins.installed.microsoft_commerce.services.mapping import map_product
from plugins.installed.microsoft_commerce.services.settings import microsoft_settings
from plugins.installed.microsoft_commerce.templatetags.microsoft_commerce import uet_tag

User = get_user_model()
_G = '{http://base.google.com/ns/1.0}'
_GIF = (
    b'GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!'
    b'\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;'
)


def _plugin():
    from plugins.registry import plugin_registry

    for attr in ('get', 'get_plugin'):
        fn = getattr(plugin_registry, attr, None)
        if callable(fn):
            try:
                p = fn('microsoft_commerce')
            except Exception:  # noqa: BLE001
                p = None
            if p is not None:
                return p
    from plugins.installed.microsoft_commerce.plugin import MicrosoftCommercePlugin

    return MicrosoftCommercePlugin()


def _product(slug, sku):
    p = Product.objects.create(
        name=slug.title(),
        slug=slug,
        sku=sku,
        price=Money(Decimal('9.00'), 'USD'),
        product_type='simple',
        status='active',
    )
    ProductImage(product=p, is_primary=True).image.save(f'{slug}.gif', ContentFile(_GIF), save=True)
    return p


class FeedTests(TestCase):
    def test_feed_and_endpoint(self):
        _product('dune', 'SKU1')
        item = map_product(Product.objects.get(slug='dune'), microsoft_settings())
        self.assertEqual(item['availability'], 'in stock')
        xml, stats = build_feed(log=False)
        self.assertEqual(stats['items'], 1)
        self.assertIsNotNone(ET.fromstring(xml).find(f'.//item/{_G}price'))
        r = Client().get('/feeds/microsoft-catalog.xml')
        self.assertEqual(r.status_code, 200)
        self.assertIn('application/xml', r['Content-Type'])


class UetTests(TestCase):
    def setUp(self):
        _plugin().invalidate_config_cache()

    def tearDown(self):
        _plugin().invalidate_config_cache()

    def _enable(self, tag_id='12345678'):
        p = _plugin()
        p.set_config('uet_enabled', True)
        p.set_config('uet_tag_id', tag_id)
        p.invalidate_config_cache()

    def test_disabled(self):
        self.assertEqual(uet_tag(Context({'request': RequestFactory().get('/')})), '')

    def test_invalid_tag(self):
        self._enable(tag_id='abc')
        self.assertEqual(uet_tag(Context({'request': RequestFactory().get('/')})), '')

    def test_enabled_emits_uet(self):
        self._enable()
        html = uet_tag(Context({'request': RequestFactory().get('/')}))
        self.assertIn('bat.bing.com/bat.js', html)
        self.assertIn('"12345678"', html)
        self.assertIn('pageLoad', html)

    def test_purchase_on_confirmation(self):
        self._enable()
        order = type('O', (), {'order_number': 'A-1', 'total': Money(Decimal('25'), 'USD')})()
        ctx = Context({'request': RequestFactory().get('/order/confirmation/A-1/'), 'order': order})
        html = uet_tag(ctx)
        self.assertIn('"event","purchase"', html.replace(' ', ''))
        self.assertIn('"revenue_value": 25.0', html)
        self.assertIn('"transaction_id": "A-1"', html)

    def test_purchase_not_off_confirmation(self):
        self._enable()
        order = type('O', (), {'order_number': 'A-1', 'total': Money(Decimal('25'), 'USD')})()
        ctx = Context({'request': RequestFactory().get('/'), 'order': order})
        self.assertNotIn('purchase', uet_tag(ctx))

    def test_remarketing_pagetype_home(self):
        self._enable()
        html = uet_tag(Context({'request': RequestFactory().get('/')}))
        self.assertIn('"ecomm_pagetype": "home"', html)

    def test_remarketing_product_page_carries_prodid_and_value(self):
        self._enable()
        p = _product('dune', 'SKU-D')
        ctx = Context({'request': RequestFactory().get('/products/dune/'), 'product': p})
        html = uet_tag(ctx)
        self.assertIn('"ecomm_pagetype": "product"', html)
        self.assertIn('"ecomm_prodid": "SKU-D"', html)  # matches feed id
        self.assertIn('"ecomm_totalvalue": 9.0', html)

    def test_xss_safe_tag_id(self):
        # Non-numeric ids are rejected by the regex; nothing renders.
        self._enable(tag_id='1"/></script><script>alert(1)</script>')
        self.assertEqual(uet_tag(Context({'request': RequestFactory().get('/')})), '')


class AdsSoapTests(TestCase):
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
            'oauth_client_id': 'cid',
            'oauth_client_secret': 'sec',
            'oauth_refresh_token': 'ref',
            'developer_token': 'dev',
            'customer_id': '111',
            'account_id': '222',
        }.items():
            p.set_config(k, v)
        p.invalidate_config_cache()

    def test_not_connected(self):
        from plugins.installed.microsoft_commerce.services.ads_api import list_campaigns

        self.assertEqual(list_campaigns()['reason'], 'not_connected')

    def test_list_campaigns_parses_soap(self):
        from unittest.mock import MagicMock, patch

        from plugins.installed.microsoft_commerce.services.ads_api import list_campaigns

        self._connect()
        token = MagicMock()
        token.json.return_value = {'access_token': 'T'}
        token.raise_for_status.return_value = None
        soap = MagicMock()
        soap.content = (
            b'<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope">'
            b'<s:Body><GetCampaignsByAccountIdResponse xmlns="https://bingads.microsoft.com/CampaignManagement/v13">'
            b'<Campaigns><Campaign><Id>123</Id><Name>Shopping</Name><Status>Active</Status>'
            b'<DailyBudget>20</DailyBudget></Campaign></Campaigns>'
            b'</GetCampaignsByAccountIdResponse></s:Body></s:Envelope>'
        )
        soap.raise_for_status.return_value = None
        with patch('requests.post', side_effect=[token, soap]) as post:
            rep = list_campaigns()
        self.assertTrue(rep['ok'])
        c = rep['campaigns'][0]
        self.assertEqual(c['id'], '123')
        self.assertEqual(c['name'], 'Shopping')
        self.assertEqual(c['status'], 'Active')
        self.assertIn('CampaignManagementService', post.call_args.args[0])

    def test_soap_fault_surfaced(self):
        from unittest.mock import MagicMock, patch

        from plugins.installed.microsoft_commerce.services.ads_api import list_campaigns

        self._connect()
        token = MagicMock()
        token.json.return_value = {'access_token': 'T'}
        token.raise_for_status.return_value = None
        fault = MagicMock()
        fault.content = (
            b'<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"><s:Body><s:Fault>'
            b'<faultstring>Invalid developer token</faultstring></s:Fault></s:Body></s:Envelope>'
        )
        fault.raise_for_status.return_value = None
        with patch('requests.post', side_effect=[token, fault]):
            rep = list_campaigns()
        self.assertFalse(rep['ok'])
        self.assertIn('developer token', rep['reason'])

    def test_status_and_id_validation(self):
        from plugins.installed.microsoft_commerce.services.ads_api import set_campaign_status

        self._connect()
        self.assertEqual(set_campaign_status('1', 'BOGUS')['reason'], 'bad_status')
        self.assertEqual(set_campaign_status('../x', 'Active')['reason'], 'bad_campaign_id')


class DashboardTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username='s', email='s@x.test', password='pw', is_staff=True
        )

    def _staff(self):
        c = Client()
        c.force_login(self.staff)
        return c

    def test_boundary_and_render(self):
        self.assertEqual(
            Client().get('/dashboard/apps/microsoft_commerce/overview/').status_code, 302
        )
        r = self._staff().get('/dashboard/apps/microsoft_commerce/overview/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'microsoft-catalog.xml')

    def test_ads_dashboard_renders_unconnected(self):
        self.assertEqual(Client().get('/dashboard/apps/microsoft_commerce/ads/').status_code, 302)
        r = self._staff().get('/dashboard/apps/microsoft_commerce/ads/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Connect Microsoft Ads')
