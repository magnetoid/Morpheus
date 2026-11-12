"""Which carrier rate a label is bought at (the Shipping page's ``label_rate``, v0.155.0).

v0.154.0 always bought the cheapest rate the carrier offered.
"""

from __future__ import annotations

from django.test import TestCase

from morpheus.core import MorpheusEvents, hook_registry
from plugins.installed.shipping.labels import LabelError, _choose_rate
from plugins.registry import app_registry

SHIPPO = [
    {
        'object_id': 'r-express',
        'amount': '12.40',
        'provider': 'DHL',
        'servicelevel': {'name': 'Express'},
        'estimated_days': 1,
    },
    {
        'object_id': 'r-cheap',
        'amount': '6.10',
        'provider': 'Deutsche Post',
        'servicelevel': {'name': 'Paket'},
        'estimated_days': 4,
    },
    {'object_id': 'r-dhl', 'amount': '8.00', 'provider': 'DHL', 'servicelevel': {'name': 'Paket'}},
]
EASYPOST = [
    {
        'id': 'e-fast',
        'rate': '20.00',
        'carrier': 'UPS',
        'service': 'NextDayAir',
        'delivery_days': 1,
    },
    {'id': 'e-slow', 'rate': '7.00', 'carrier': 'USPS', 'service': 'Ground', 'delivery_days': 5},
]


class LabelRateTests(TestCase):
    def setUp(self):
        self.shipping = app_registry.get('shipping')
        self.addCleanup(self.shipping.invalidate_config_cache)

    def _set(self, **values):
        for key, value in values.items():
            self.shipping.set_config(key, value)

    def test_the_cheapest_by_default(self):
        self.assertEqual(_choose_rate(SHIPPO, 'shippo', 'Shippo')['object_id'], 'r-cheap')
        self.assertEqual(_choose_rate(EASYPOST, 'easypost', 'EasyPost')['id'], 'e-slow')

    def test_the_fastest(self):
        self._set(label_rate='fastest')
        self.assertEqual(_choose_rate(SHIPPO, 'shippo', 'Shippo')['object_id'], 'r-express')
        self.assertEqual(_choose_rate(EASYPOST, 'easypost', 'EasyPost')['id'], 'e-fast')

    def test_the_preferred_carrier_and_service(self):
        self._set(label_rate='preferred', label_carrier='dhl', label_service='')
        self.assertEqual(_choose_rate(SHIPPO, 'shippo', 'Shippo')['object_id'], 'r-dhl')
        self._set(label_service='Express')
        self.assertEqual(_choose_rate(SHIPPO, 'shippo', 'Shippo')['object_id'], 'r-express')

    def test_a_preferred_carrier_not_offered_is_refused_with_what_was(self):
        self._set(label_rate='preferred', label_carrier='FedEx', label_service='')
        with self.assertRaises(LabelError) as caught:
            _choose_rate(SHIPPO, 'shippo', 'Shippo')
        self.assertIn('FedEx', str(caught.exception))
        self.assertIn('Deutsche Post Paket', str(caught.exception))

    def test_an_app_may_pick_another_offered_rate_but_not_invent_one(self):
        answers = iter([SHIPPO[0], {'object_id': 'made-up', 'amount': '0'}])

        def pick(value, rates=None, **kwargs):
            return next(answers)

        hook_registry.register(MorpheusEvents.SHIPPING_LABEL_RATE, pick, plugin=None)
        self.addCleanup(hook_registry.unregister, MorpheusEvents.SHIPPING_LABEL_RATE, pick)
        self.assertEqual(_choose_rate(SHIPPO, 'shippo', 'Shippo')['object_id'], 'r-express')
        self.assertEqual(_choose_rate(SHIPPO, 'shippo', 'Shippo')['object_id'], 'r-cheap')
