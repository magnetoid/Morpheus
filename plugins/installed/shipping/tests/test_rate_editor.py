"""Every kind of rate can be entered, in the store's currency (v0.154.0).

The Shipping page took a flat amount only, priced it in USD whatever the store
sold in, and an edit kept a field the merchant had emptied.
"""

# ruff: noqa: PLC0415
from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from djmoney.money import Money


@override_settings(STORE_CURRENCY='EUR')
class RateValuesTests(TestCase):
    def _values(self, **kwargs):
        from plugins.installed.shipping.rates import rate_values

        return rate_values(**kwargs)

    def test_flat_is_priced_in_the_store_currency(self):
        values = self._values(computation='flat', flat_amount='4.5')
        self.assertEqual(values['flat_amount'], Money(Decimal('4.50'), 'EUR'))
        self.assertIsNone(values['free_threshold'])
        self.assertEqual(values['tiers'], [])

    def test_free_over_needs_both_amounts(self):
        from plugins.installed.shipping.rates import RateError

        values = self._values(computation='free_over', flat_amount='5', free_threshold='40')
        self.assertEqual(values['free_threshold'], Money(Decimal('40.00'), 'EUR'))
        with self.assertRaisesMessage(RateError, 'Free over is required'):
            self._values(computation='free_over', flat_amount='5')
        with self.assertRaisesMessage(RateError, 'more than 0'):
            self._values(computation='free_over', flat_amount='5', free_threshold='0')

    def test_tiers_are_sorted_and_must_start_at_zero(self):
        from plugins.installed.shipping.rates import RateError

        values = self._values(computation='weight_tier', tiers=[('2', '9'), ('0', '4'), ('', '')])
        self.assertEqual(
            values['tiers'],
            [{'threshold': '0.00', 'amount': '4.00'}, {'threshold': '2.00', 'amount': '9.00'}],
        )
        for tiers, message in (
            ([('1', '4')], 'Start the first tier at 0'),
            ([('0', '4'), ('0', '5')], 'same point'),
            ([('0', '')], 'price of a tier is required'),
            ([], 'at least one tier'),
        ):
            with self.subTest(tiers=tiers), self.assertRaisesMessage(RateError, message):
                self._values(computation='order_total_tier', tiers=tiers)

    def test_bad_numbers_are_refused(self):
        from plugins.installed.shipping.rates import RateError

        for kwargs, message in (
            ({'computation': 'flat', 'flat_amount': '-1'}, 'cannot be negative'),
            ({'computation': 'flat', 'flat_amount': 'abc'}, 'must be a number'),
            ({'computation': 'flat', 'flat_amount': 'NaN'}, 'must be a number'),
            ({'computation': 'flat', 'flat_amount': '1000000000000'}, 'too large'),
            ({'computation': 'flat', 'flat_amount': 1e30}, 'too large'),
            ({'computation': 'flat'}, 'Price is required'),
            ({'computation': 'teleport'}, 'Choose how this rate is priced'),
            (
                {
                    'computation': 'flat',
                    'flat_amount': '1',
                    'estimated_days_min': '5',
                    'estimated_days_max': '2',
                },
                'cannot be slower',
            ),
        ):
            with self.subTest(kwargs=kwargs), self.assertRaisesMessage(RateError, message):
                self._values(**kwargs)

    def test_pickup_is_free_unless_it_has_a_fee(self):
        self.assertEqual(self._values(computation='pickup')['flat_amount'], Money(0, 'EUR'))
        self.assertEqual(
            self._values(computation='pickup', flat_amount='2')['flat_amount'], Money(2, 'EUR')
        )

    def test_a_kind_clears_what_it_does_not_use(self):
        values = self._values(computation='weight_tier', flat_amount='5', tiers=[('0', '3')])
        self.assertIsNone(values['flat_amount'])


@override_settings(STORE_CURRENCY='EUR')
class RateEditorPageTests(TestCase):
    def setUp(self):
        from plugins.installed.shipping.models import ShippingZone

        staff = get_user_model().objects.create_user(
            username='ship', email='ship@example.com', password='x', is_staff=True
        )
        self.client.force_login(staff)
        self.url = reverse('shipping_dashboard:zones')
        self.zone = ShippingZone.objects.create(name='EU', countries=['DE', 'FR'])

    def _post(self, **fields):
        data = {'kind': 'rate', 'zone': str(self.zone.pk), 'is_active': 'on', **fields}
        return self.client.post(self.url, data)

    def test_a_tiered_rate_is_created_from_the_form(self):
        from plugins.installed.shipping.models import ShippingRate

        self.client.post(
            self.url,
            {
                'kind': 'rate',
                'action': 'create',
                'name': 'By weight',
                'zone': str(self.zone.pk),
                'computation': 'weight_tier',
                'tier_threshold': ['0', '2', ''],
                'tier_amount': ['4', '9', ''],
                'estimated_days_min': '2',
                'estimated_days_max': '4',
                'priority': '10',
                'is_active': 'on',
            },
        )
        rate = ShippingRate.objects.get(name='By weight')
        self.assertEqual(len(rate.tiers), 2)
        self.assertEqual((rate.estimated_days_min, rate.estimated_days_max), (2, 4))
        page = self.client.get(self.url).content.decode()
        self.assertIn('From 4.00 EUR · 2 tiers by weight', page)
        self.assertIn('Price (EUR)', page)

    def test_free_over_is_saved_in_eur(self):
        from plugins.installed.shipping.models import ShippingRate

        self._post(
            action='create',
            name='Standard',
            computation='free_over',
            flat_amount='4.90',
            free_threshold='39',
        )
        rate = ShippingRate.objects.get(name='Standard')
        self.assertEqual(rate.flat_amount, Money(Decimal('4.90'), 'EUR'))
        self.assertEqual(rate.free_threshold, Money(Decimal('39.00'), 'EUR'))

    def test_an_edit_saves_the_whole_form(self):
        from plugins.installed.shipping.models import ShippingRate

        rate = ShippingRate.objects.create(
            zone=self.zone,
            name='Old',
            computation='free_over',
            flat_amount=Money(5, 'USD'),
            free_threshold=Money(50, 'USD'),
            estimated_days_min=3,
        )
        self._post(
            action='edit',
            rate_id=str(rate.pk),
            name='Flat now',
            computation='flat',
            flat_amount='6',
        )
        rate.refresh_from_db()
        self.assertEqual(rate.name, 'Flat now')
        self.assertEqual(rate.flat_amount, Money(6, 'EUR'))
        self.assertIsNone(rate.free_threshold)
        self.assertIsNone(rate.estimated_days_min)

    def test_a_bad_rate_saves_nothing_and_says_why(self):
        from plugins.installed.shipping.models import ShippingRate

        response = self.client.post(
            self.url,
            {
                'kind': 'rate',
                'action': 'create',
                'name': 'Broken',
                'zone': str(self.zone.pk),
                'computation': 'flat',
                'flat_amount': '-3',
            },
            follow=True,
        )
        self.assertFalse(ShippingRate.objects.filter(name='Broken').exists())
        self.assertContains(response, 'Price cannot be negative.')

    def test_carrier_keys_are_never_shown(self):
        from plugins.models import PluginConfig

        self.client.post(self.url, {'kind': 'config', 'shippo_api_key': 'shippo_live_secret'})
        page = self.client.get(self.url).content.decode()
        self.assertNotIn('shippo_live_secret', page)
        self.assertIn('Saved; leave blank to keep it', page)
        # A blank field keeps the key; the box removes it.
        self.client.post(self.url, {'kind': 'config', 'shippo_api_key': ''})
        cfg = PluginConfig.objects.get(plugin_name='shipping').config
        self.assertEqual(cfg['shippo_api_key'], 'shippo_live_secret')
        self.client.post(
            self.url, {'kind': 'config', 'shippo_api_key': '', 'clear_shippo_api_key': 'on'}
        )
        cfg = PluginConfig.objects.get(plugin_name='shipping').config
        self.assertEqual(cfg['shippo_api_key'], '')


@override_settings(STORE_CURRENCY='EUR')
class SetRateToolTests(TestCase):
    def setUp(self):
        from plugins.installed.shipping.models import ShippingZone

        self.zone = ShippingZone.objects.create(name='EU', countries=['DE'])

    def _call(self, **kwargs):
        from plugins.installed.shipping.agent_tools import set_rate_tool

        return set_rate_tool.invoke(kwargs)

    def test_creates_then_updates_by_name(self):
        from plugins.installed.shipping.models import ShippingRate

        first = self._call(
            zone_name='eu', name='Standard', computation='flat', price=5, days_min=2, days_max=4
        )
        self.assertTrue(first.output['created'])
        second = self._call(
            zone_name='EU', name='standard', computation='free_over', price=5, free_over=40
        )
        self.assertFalse(second.output['created'])
        rate = ShippingRate.objects.get()
        self.assertEqual(rate.free_threshold, Money(40, 'EUR'))
        self.assertEqual((rate.estimated_days_min, rate.estimated_days_max), (2, 4))
        self.assertEqual(second.output['charges'], '5.00 EUR · free over 40.00 EUR')

    def test_tiers_and_refusals(self):
        from morpheus.core import ToolError

        result = self._call(
            zone_name='EU',
            name='By total',
            computation='order_total_tier',
            tiers=[{'from': 0, 'price': 6}, {'from': 50, 'price': 0}],
        )
        self.assertIn('2 tiers by order total', result.output['charges'])
        free_first = self._call(
            zone_name='EU',
            name='By weight',
            computation='weight_tier',
            tiers=[{'from': 0, 'price': 0}, {'from': 2, 'price': 5}],
        )
        self.assertIn('From 0.00 EUR · 2 tiers by weight', free_first.output['charges'])
        with self.assertRaisesMessage(ToolError, 'Unknown shipping zone'):
            self._call(zone_name='Mars', name='X', computation='flat', price=1)
        with self.assertRaisesMessage(ToolError, 'Shipping page'):
            self._call(zone_name='EU', name='X', computation='carrier_shippo')
        with self.assertRaisesMessage(ToolError, 'Price is required'):
            self._call(zone_name='EU', name='X', computation='flat')

    def test_writes_need_approval(self):
        from plugins.installed.shipping.agent_tools import (
            add_flat_rate_tool,
            buy_label_tool,
            set_rate_tool,
        )

        for t in (set_rate_tool, buy_label_tool, add_flat_rate_tool):
            self.assertTrue(t.requires_approval, t.name)
            self.assertEqual(t.scopes, ['shipping.write'])

    def test_add_flat_rate_uses_the_store_currency(self):
        from plugins.installed.shipping.agent_tools import add_flat_rate_tool
        from plugins.installed.shipping.models import ShippingRate

        add_flat_rate_tool.invoke({'zone_name': 'EU', 'name': 'Flat', 'amount': 3})
        self.assertEqual(ShippingRate.objects.get().flat_amount, Money(3, 'EUR'))
