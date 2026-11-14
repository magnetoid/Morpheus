"""Who pays for a return, how it is sent and what refund it earns (v0.163.0).

Each is stated only once the merchant sets it in this app's settings, with the
values Google's merchant return policy page names
(https://developers.google.com/search/docs/appearance/structured-data/return-policy),
and the same policy goes on the store's node and on every offer, a variant's too.
"""

# ruff: noqa: PLC0415
from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

from django.test import TestCase
from djmoney.money import Money

from core.models import StoreSettings
from plugins.installed.catalog.models import Product

_S = 'https://schema.org/'


def _graph():
    return {
        '@graph': [
            {'@type': 'OnlineStore', '@id': 'https://shop.test/#organization'},
            {
                '@type': 'ProductGroup',
                'hasVariant': [
                    {'@type': 'Product', 'offers': {'@type': 'Offer'}},
                    {'@type': 'Product', 'offers': {'@type': 'Offer'}},
                ],
            },
        ]
    }


class ReturnTermsTests(TestCase):
    def setUp(self):
        store = StoreSettings.objects.first() or StoreSettings.objects.create()
        store.country = 'ME'
        store.save()
        Product.objects.create(
            name='Parcel Book',
            slug='parcel-book',
            sku='PB-1',
            price=Money(Decimal('12.00'), 'EUR'),
            product_type='simple',
            status='active',
            requires_shipping=True,
        )

    def _configure(self, **values):
        from plugins.registry import app_registry

        plugin = app_registry.get('returns_portal')
        for key, value in values.items():
            plugin.set_config(key, value)
        self.addCleanup(plugin.invalidate_config_cache)

    def _policies(self):
        from plugins.installed.returns_portal.seo_graph import on_seo_jsonld_graph

        page = SimpleNamespace(obj=SimpleNamespace(product_type='simple', requires_shipping=True))
        graph = on_seo_jsonld_graph(_graph(), page=page)
        store = graph['@graph'][0]['hasMerchantReturnPolicy']
        offers = [m['offers']['hasMerchantReturnPolicy'] for m in graph['@graph'][1]['hasVariant']]
        return store, offers

    def test_unset_states_only_the_window(self):
        store, offers = self._policies()
        for policy in (store, *offers):
            self.assertEqual(policy['merchantReturnDays'], 30)
            for key in ('returnFees', 'returnMethod', 'refundType', 'returnShippingFeesAmount'):
                self.assertNotIn(key, policy)

    def test_set_terms_are_on_the_store_and_every_offer(self):
        self._configure(
            return_fees='free',
            return_by_mail=True,
            return_in_store=True,
            refund_full=True,
        )
        store, offers = self._policies()
        for policy in (store, *offers):
            self.assertEqual(policy['returnFees'], f'{_S}FreeReturn')
            self.assertEqual(policy['returnMethod'], [f'{_S}ReturnByMail', f'{_S}ReturnInStore'])
            self.assertEqual(policy['refundType'], f'{_S}FullRefund')
        self.assertEqual(store, offers[0])

    def test_a_fixed_fee_needs_its_amount(self):
        self._configure(return_fees='fixed_fee', return_shipping_fee=0)
        store, _offers = self._policies()
        self.assertNotIn('returnFees', store)

        self._configure(return_fees='fixed_fee', return_shipping_fee='4.50')
        store, _offers = self._policies()
        self.assertEqual(store['returnFees'], f'{_S}ReturnShippingFees')
        self.assertEqual(store['returnShippingFeesAmount']['value'], '4.50')
        self.assertEqual(store['returnShippingFeesAmount']['currency'], 'EUR')

    def test_customer_pays_and_store_credit(self):
        self._configure(
            return_fees='customer_pays', refund_store_credit='true', return_at_kiosk='on'
        )
        store, _offers = self._policies()
        self.assertEqual(store['returnFees'], f'{_S}ReturnFeesCustomerResponsibility')
        self.assertEqual(store['refundType'], f'{_S}StoreCreditRefund')
        self.assertEqual(store['returnMethod'], f'{_S}ReturnAtKiosk')

    def test_no_returns_states_no_terms(self):
        self._configure(return_window_days=0, return_fees='free', refund_full=True)
        store, _offers = self._policies()
        self.assertEqual(store['returnPolicyCategory'], f'{_S}MerchantReturnNotPermitted')
        self.assertNotIn('returnFees', store)
        self.assertNotIn('refundType', store)

    def test_every_setting_is_in_the_panel_schema(self):
        from plugins.registry import app_registry

        schema = app_registry.get('returns_portal').get_config_schema()['properties']
        for key in (
            'return_fees',
            'return_shipping_fee',
            'return_by_mail',
            'return_in_store',
            'return_at_kiosk',
            'refund_full',
            'refund_exchange',
            'refund_store_credit',
        ):
            self.assertIn(key, schema)
        self.assertEqual(schema['return_fees']['default'], 'not_stated')
