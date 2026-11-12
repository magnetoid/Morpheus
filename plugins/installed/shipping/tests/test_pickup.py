"""A pickup rate: the customer collects the order, free or for a fee (v0.154.0)."""

# ruff: noqa: PLC0415
from __future__ import annotations

from django.template.loader import render_to_string
from django.test import TestCase
from djmoney.money import Money

from plugins.installed.shipping.models import ShippingRate, ShippingZone


class PickupTests(TestCase):
    def setUp(self):
        self.zone = ShippingZone.objects.create(name='Local', countries=['ME'])

    def _rate(self, **fields):
        return ShippingRate.objects.create(
            zone=self.zone, name='Collect in Kotor', computation='pickup', **fields
        )

    def test_quote_is_its_fee_or_nothing(self):
        from plugins.installed.shipping.services import _quote_one

        free = self._rate()
        self.assertEqual(_quote_one(free, subtotal=Money(30, 'EUR')), Money(0, 'EUR'))
        paid = self._rate(flat_amount=Money(2, 'EUR'))
        self.assertEqual(_quote_one(paid, subtotal=Money(30, 'EUR')), Money(2, 'EUR'))

    def test_pickup_is_never_stated_as_shipping(self):
        from plugins.installed.shipping.seo_graph import shipping_details

        self._rate(flat_amount=Money(0, 'EUR'), priority=1)
        self.assertEqual(shipping_details(currency='EUR'), [])
        ShippingRate.objects.create(
            zone=self.zone,
            name='Courier',
            computation='flat',
            flat_amount=Money(6, 'EUR'),
            priority=5,
        )
        (block,) = shipping_details(currency='EUR')
        self.assertEqual(block['shippingRate']['value'], '6.00')

    def test_the_shipping_page_lists_it(self):
        from plugins.installed.shipping.templatetags.shipping import shipping_rate_cards

        self._rate(flat_amount=Money(0, 'EUR'))
        (card,) = shipping_rate_cards()
        self.assertEqual(card['name'], 'Collect in Kotor')
        price = render_to_string('shipping/blocks/_rate_price.html', {'c': card})
        self.assertIn('Free', price)


class VariantOfferShippingTests(TestCase):
    """A multi-edition product keeps its offers on `hasVariant`, not the group."""

    def _graph(self):
        offer = lambda p: {'@type': 'Offer', 'price': p, 'priceCurrency': 'EUR'}  # noqa: E731
        return {
            '@graph': [
                {
                    '@type': 'ProductGroup',
                    'hasVariant': [
                        {'@type': 'Product', 'offers': offer('5.00')},
                        {'@type': 'Product', 'offers': offer('9.00')},
                    ],
                }
            ]
        }

    def _page(self):
        from types import SimpleNamespace

        return SimpleNamespace(obj=SimpleNamespace(product_type='simple', requires_shipping=True))

    def test_every_variant_offer_carries_shipping_when_a_rate_exists(self):
        from plugins.installed.shipping.seo_graph import on_seo_jsonld_graph

        zone = ShippingZone.objects.create(name='EU', countries=['ME'])
        ShippingRate.objects.create(
            zone=zone, name='Courier', computation='flat', flat_amount=Money(6, 'EUR')
        )
        graph = on_seo_jsonld_graph(self._graph(), page=self._page())
        for member in graph['@graph'][0]['hasVariant']:
            self.assertEqual(member['offers']['shippingDetails']['shippingRate']['value'], '6.00')

    def test_nothing_is_claimed_without_a_rate(self):
        from plugins.installed.shipping.seo_graph import on_seo_jsonld_graph

        graph = on_seo_jsonld_graph(self._graph(), page=self._page())
        for member in graph['@graph'][0]['hasVariant']:
            self.assertNotIn('shippingDetails', member['offers'])
