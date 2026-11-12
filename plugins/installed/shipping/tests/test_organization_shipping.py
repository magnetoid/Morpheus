"""The store's shipping policy on its Organization node, and its handling time (v0.163.0).

Google reads `hasShippingService` on the Organization for every product the
store sells (https://developers.google.com/search/docs/appearance/structured-data/shipping-policy)
and `deliveryTime.handlingTime` on each offer
(https://developers.google.com/search/docs/appearance/structured-data/merchant-listing).
Both come from this app's rates and the merchant's own handling time; nothing is
claimed that the Shipping page does not hold.
"""

# ruff: noqa: PLC0415
from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.test import TestCase
from djmoney.money import Money

from plugins.installed.catalog.models import Product
from plugins.installed.shipping.models import ShippingRate, ShippingZone


def _graph():
    return {
        '@graph': [
            {'@type': 'OnlineStore', '@id': 'https://shop.test/#organization', 'name': 'Shop'},
            {
                '@type': 'ProductGroup',
                'hasVariant': [
                    {'@type': 'Product', 'offers': {'@type': 'Offer', 'priceCurrency': 'EUR'}},
                    {'@type': 'Product', 'offers': {'@type': 'Offer', 'priceCurrency': 'EUR'}},
                ],
            },
        ]
    }


def _page():
    return SimpleNamespace(obj=SimpleNamespace(product_type='simple', requires_shipping=True))


def _set_handling(**values):
    from plugins.models import PluginConfig

    row, _ = PluginConfig.objects.get_or_create(plugin_name='shipping')
    row.config = {**(row.config or {}), **values}
    row.save()


class OrganizationShippingTests(TestCase):
    def setUp(self):
        Product.objects.create(
            name='Parcel Book',
            slug='parcel-book',
            sku='PB-1',
            price=Money(Decimal('12.00'), 'EUR'),
            product_type='simple',
            status='active',
            requires_shipping=True,
        )
        self.zone = ShippingZone.objects.create(name='EU', countries=['ME', 'HR'])

    def _enrich(self):
        from plugins.installed.shipping.seo_graph import on_seo_jsonld_graph

        return on_seo_jsonld_graph(_graph(), page=_page())

    def _store(self, graph):
        return graph['@graph'][0]

    def test_a_fixed_rate_is_the_stores_shipping_service(self):
        ShippingRate.objects.create(
            zone=self.zone,
            name='Courier',
            computation='flat',
            flat_amount=Money(6, 'EUR'),
            estimated_days_min=2,
            estimated_days_max=4,
        )
        service = self._store(self._enrich())['hasShippingService']
        self.assertEqual(service['@type'], 'ShippingService')
        self.assertEqual(service['fulfillmentType'], 'https://schema.org/FulfillmentTypeDelivery')
        conditions = service['shippingConditions']
        self.assertEqual(conditions['shippingDestination']['addressCountry'], ['ME', 'HR'])
        self.assertEqual(conditions['shippingRate']['value'], '6.00')
        self.assertEqual(conditions['transitTime']['duration']['minValue'], 2)
        self.assertEqual(conditions['transitTime']['duration']['maxValue'], 4)
        self.assertNotIn('handlingTime', service)

    def test_free_over_a_threshold_is_two_order_value_ranges(self):
        ShippingRate.objects.create(
            zone=self.zone,
            name='Standard',
            computation='free_over',
            flat_amount=Money(5, 'EUR'),
            free_threshold=Money(40, 'EUR'),
        )
        low, high = self._store(self._enrich())['hasShippingService']['shippingConditions']
        self.assertEqual(low['orderValue']['maxValue'], 39.99)
        self.assertEqual(low['shippingRate']['value'], '5.00')
        self.assertEqual(high['orderValue']['minValue'], 40.0)
        self.assertEqual(high['shippingRate']['value'], '0.00')

    def test_no_rate_no_service(self):
        self.assertNotIn('hasShippingService', self._store(self._enrich()))

    def test_carrier_tiered_and_pickup_rates_are_no_service(self):
        for computation in ('carrier_shippo', 'pickup', 'weight_tier'):
            ShippingRate.objects.create(
                zone=self.zone,
                name=computation,
                computation=computation,
                flat_amount=Money(3, 'EUR'),
                tiers=[{'amount': '4.00'}],
            )
        self.assertNotIn('hasShippingService', self._store(self._enrich()))

    def test_a_store_that_ships_nothing_states_no_service(self):
        Product.objects.update(requires_shipping=False)
        ShippingRate.objects.create(
            zone=self.zone, name='Courier', computation='flat', flat_amount=Money(6, 'EUR')
        )
        self.assertNotIn('hasShippingService', self._store(self._enrich()))


class HandlingTimeTests(TestCase):
    def setUp(self):
        Product.objects.create(
            name='Parcel Book',
            slug='parcel-book',
            sku='PB-1',
            price=Money(Decimal('12.00'), 'EUR'),
            product_type='simple',
            status='active',
            requires_shipping=True,
        )
        zone = ShippingZone.objects.create(name='EU', countries=['ME'])
        ShippingRate.objects.create(
            zone=zone,
            name='Courier',
            computation='flat',
            flat_amount=Money(6, 'EUR'),
            estimated_days_min=2,
            estimated_days_max=4,
        )

    def _enrich(self):
        from plugins.installed.shipping.seo_graph import on_seo_jsonld_graph

        return on_seo_jsonld_graph(_graph(), page=_page())

    def test_unset_claims_no_handling_time_anywhere(self):
        graph = self._enrich()
        self.assertNotIn('handlingTime', str(graph))
        offer = graph['@graph'][1]['hasVariant'][0]['offers']
        self.assertEqual(offer['shippingDetails']['deliveryTime']['transitTime']['minValue'], 2)

    def test_set_it_is_on_the_service_and_every_offer(self):
        _set_handling(handling_days_min=0, handling_days_max=1, handling_cutoff_time='14:00')
        graph = self._enrich()
        handling = graph['@graph'][0]['hasShippingService']['handlingTime']
        self.assertEqual(handling['@type'], 'ServicePeriod')
        self.assertEqual(handling['duration']['minValue'], 0)
        self.assertEqual(handling['duration']['maxValue'], 1)
        self.assertEqual(handling['duration']['unitCode'], 'DAY')
        self.assertTrue(handling['cutoffTime'].startswith('14:00:00'))
        for member in graph['@graph'][1]['hasVariant']:
            delivery = member['offers']['shippingDetails']['deliveryTime']
            self.assertEqual(delivery['handlingTime']['maxValue'], 1)
            self.assertEqual(delivery['transitTime']['maxValue'], 4)

    def test_a_value_nobody_could_have_meant_claims_nothing(self):
        # settings.set writes any string; reading it never invents a period.
        _set_handling(handling_days_min='soon', handling_days_max=3)
        self.assertNotIn('handlingTime', str(self._enrich()))

    def test_the_shipping_page_saves_and_refuses(self):
        from django.urls import reverse

        from plugins.installed.shipping.seo_graph import clean_handling

        self.assertEqual(
            clean_handling('2', '', ''),
            {'handling_days_min': 2, 'handling_days_max': 2, 'handling_cutoff_time': ''},
        )
        for bad in (('3', '1', ''), ('x', '', ''), ('', '', '25:00'), ('40', '', '')):
            with self.assertRaises(ValueError, msg=bad):
                clean_handling(*bad)

        staff = get_user_model().objects.create_superuser('ship', 'ship@x.test', 'pw')
        self.client.force_login(staff)
        url = reverse('shipping_dashboard:zones')
        self.assertContains(self.client.get(url), 'name="handling_days_min"')
        self.client.post(
            url,
            {
                'kind': 'config',
                'handling_days_min': '1',
                'handling_days_max': '2',
                'handling_cutoff_time': '15:30',
            },
        )
        from plugins.installed.shipping.services import _shipping_config

        cfg = _shipping_config()
        self.assertEqual((cfg['handling_days_min'], cfg['handling_days_max']), (1, 2))
        self.assertEqual(cfg['handling_cutoff_time'], '15:30')
        # A wrong value saves nothing at all, the carrier fields included.
        self.client.post(
            url,
            {
                'kind': 'config',
                'handling_days_min': '5',
                'handling_days_max': '1',
                'label_carrier': 'dhl',
            },
        )
        cfg = _shipping_config()
        self.assertEqual(cfg['handling_days_max'], 2)
        self.assertNotEqual(cfg.get('label_carrier'), 'dhl')

    def test_linda_sees_the_handling_time(self):
        from plugins.installed.shipping.agent_tools import list_zones_tool

        _set_handling(handling_days_min=1, handling_days_max=2)
        out = list_zones_tool.invoke({}).output
        self.assertEqual(out['handling_time']['handling_days_max'], 2)
