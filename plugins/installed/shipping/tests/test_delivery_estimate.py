"""The delivery estimate shipping hands to checkout and the order (F5).

Range = the store's handling days + the rate's transit days, read the way the
structured data reads them (`seo_graph._transit_days`, `handling_days`), so the
page and the graph never disagree. Off until the merchant switches on
`show_delivery_estimate`.
"""

# ruff: noqa: PLC0415
from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from djmoney.money import Money

from plugins.installed.catalog.models import Product
from plugins.installed.orders.models import Cart, CartItem
from plugins.installed.shipping.models import ShippingRate, ShippingZone

ADDRESS = {'country': 'ME', 'region': ''}


def _config(**values):
    from plugins.models import PluginConfig

    row, _ = PluginConfig.objects.get_or_create(plugin_name='shipping')
    row.config = {**(row.config or {}), **values}
    row.save()


def _shipping_app():
    from plugins.registry import app_registry

    return app_registry.get('shipping')


class DeliveryEstimateTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user('buyer', 'buyer@x.test', 'pw')
        self.cart = Cart.objects.create(customer=user)
        product = Product.objects.create(
            name='Parcel Book',
            slug='parcel-book',
            sku='PB-1',
            price=Money(Decimal('12.00'), 'EUR'),
            status='active',
            requires_shipping=True,
        )
        CartItem.objects.create(
            cart=self.cart, product=product, quantity=1, unit_price=product.price
        )
        self.zone = ShippingZone.objects.create(name='EU', countries=['ME'])
        self.rate = self._rate(2, 4)

    def _rate(self, lo, hi, name='Courier'):
        return ShippingRate.objects.create(
            zone=self.zone,
            name=name,
            computation='flat',
            flat_amount=Money(6, 'EUR'),
            estimated_days_min=lo,
            estimated_days_max=hi,
        )

    def _checkout_rates(self):
        return _shipping_app().on_checkout_rates(None, cart=self.cart, address=ADDRESS)

    def _breakdown(self, meta=None, rate=None):
        value = {
            'subtotal': Money(Decimal('12.00'), 'EUR'),
            'shipping': Money(Decimal('0'), 'EUR'),
            'tax': Money(Decimal('0'), 'EUR'),
            'discount': Money(Decimal('0'), 'EUR'),
            'total': Money(Decimal('12.00'), 'EUR'),
            'currency': 'EUR',
            'meta': dict(meta or {}),
        }
        return _shipping_app().on_cart_breakdown(
            value, cart=self.cart, address=ADDRESS, shipping_rate_id=str((rate or self.rate).id)
        )

    def _rate_dict(self, rate=None):
        rate = rate or self.rate
        return next(r for r in self._checkout_rates() if r['id'] == str(rate.id))

    def test_off_by_default_no_estimate_anywhere(self):
        _config(handling_days_min=1, handling_days_max=2)
        self.assertNotIn('estimate', self._rate_dict())
        self.assertNotIn('delivery_estimate', self._breakdown()['meta'])

    def test_on_adds_handling_plus_transit(self):
        _config(show_delivery_estimate=True, handling_days_min=1, handling_days_max=2)
        self.assertEqual(self._rate_dict()['estimate'], {'min': 3, 'max': 6})
        self.assertEqual(self._breakdown()['meta']['delivery_estimate'], {'min': 3, 'max': 6})

    def test_no_handling_is_transit_only(self):
        _config(show_delivery_estimate=True)
        self.assertEqual(self._rate_dict()['estimate'], {'min': 2, 'max': 4})

    def test_lone_max_stands_for_both(self):
        _config(show_delivery_estimate=True)
        rate = self._rate(None, 5, name='Slow')
        self.assertEqual(self._rate_dict(rate)['estimate'], {'min': 5, 'max': 5})

    def test_rate_without_days_has_none(self):
        _config(show_delivery_estimate=True, handling_days_min=1, handling_days_max=2)
        rate = self._rate(None, None, name='Unknown')
        self.assertNotIn('estimate', self._rate_dict(rate))
        self.assertNotIn('delivery_estimate', self._breakdown(rate=rate)['meta'])

    def test_a_range_the_order_cannot_keep_is_not_shown(self):
        _config(show_delivery_estimate=True, handling_days_min=10, handling_days_max=10)
        rate = self._rate(350, 360, name='Very slow')
        self.assertNotIn('estimate', self._rate_dict(rate))
        self.assertNotIn('delivery_estimate', self._breakdown(rate=rate)['meta'])

    def test_free_shipping_still_stamps(self):
        _config(show_delivery_estimate=True)
        out = self._breakdown(meta={'free_shipping': True})
        self.assertEqual(out['shipping'].amount, Decimal('0'))
        self.assertEqual(out['meta']['delivery_estimate'], {'min': 2, 'max': 4})

    def test_matches_the_graph(self):
        from plugins.installed.shipping import seo_graph

        _config(show_delivery_estimate=True, handling_days_min=1, handling_days_max=3)
        transit = seo_graph._transit_days(self.rate)
        handling = seo_graph.handling_days()
        self.assertEqual(
            seo_graph.delivery_estimate(self.rate.estimated_days_min, self.rate.estimated_days_max),
            {'min': transit[0] + handling[0], 'max': transit[1] + handling[1]},
        )

    def test_setting_is_declared_and_agent_writable(self):
        from plugins import config_schema

        prop = config_schema.properties(_shipping_app())['show_delivery_estimate']
        self.assertEqual(prop['type'], 'boolean')
        self.assertIs(prop['default'], False)
        self.assertTrue(config_schema.agent_writable('show_delivery_estimate', prop))

    def test_shipping_page_saves_the_box(self):
        from plugins.installed.shipping.services import _shipping_config

        staff = get_user_model().objects.create_superuser('ship', 'ship@x.test', 'pw')
        self.client.force_login(staff)
        url = reverse('shipping_dashboard:zones')
        self.assertContains(self.client.get(url), 'name="show_delivery_estimate"')
        self.client.post(url, {'kind': 'config', 'show_delivery_estimate': 'on'})
        self.assertIs(_shipping_config()['show_delivery_estimate'], True)
        self.client.post(url, {'kind': 'config'})
        self.assertIs(_shipping_config()['show_delivery_estimate'], False)
