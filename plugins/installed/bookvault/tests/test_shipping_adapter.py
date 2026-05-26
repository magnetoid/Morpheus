"""Integration test: shipping plugin's carrier_bookvault adapter.

Verifies the wiring between shipping/services._bookvault_quote and
bookvault/services.get_shipping_rates — the path checkout uses to
quote live POD shipping for any book cart.
"""
from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch, MagicMock

from django.test import TestCase
from djmoney.money import Money

from plugins.installed.shipping import services as ship_services
from plugins.installed.shipping.models import ShippingRate, ShippingZone


def _seed_bv_config():
    from plugins.models import PluginConfig
    cfg, _ = PluginConfig.objects.update_or_create(
        plugin_name='bookvault',
        defaults={'is_enabled': True},
    )
    cfg.config = {
        'token': 'tok-test', 'store_id': '42', 'authenticated': True,
        'auto_send_on_paid': True,
    }
    cfg.save()


class CarrierBookvaultAdapterTests(TestCase):
    """_bookvault_quote returns the cheapest BV service as Money,
    or None when the cart has no ISBN-13 lines / BV is down."""

    def setUp(self):
        _seed_bv_config()
        self.zone = ShippingZone.objects.create(
            name='UK', countries=['GB'], is_default=False,
        )
        self.rate = ShippingRate.objects.create(
            zone=self.zone, name='Bookvault POD',
            computation='carrier_bookvault',
            is_active=True,
        )

    def _fake_cart(self, *, isbn: str | None = '9781234567890', country='GB', postcode='SW1A 1AA'):
        """Build a minimal cart-shaped object _bookvault_quote can read."""
        class FakeItem:
            quantity = 1
            unit_price = Money(Decimal('10.00'), 'USD')
            class product:
                weight = None
                weight_unit = 'kg'
                sku = isbn or ''
            variant = None
        class Items:
            @staticmethod
            def all(): return [FakeItem()]
            @staticmethod
            def select_related(*a, **k): return Items
        class FakeCart:
            metadata = {'shipping_address': {'country': country, 'zip': postcode}}
            items = Items()
        cart = FakeCart()
        # Attach to the rate exactly the way list_available_rates does.
        self.rate._cart = cart
        self.rate._country = country
        return cart

    def test_returns_cheapest_service(self):
        self._fake_cart()
        # Two BV services come back; the cheapest wins.
        with patch(
            'plugins.installed.bookvault.services.get_shipping_rates',
            return_value=[
                {'id': 'STD', 'name': 'Standard', 'detail': '', 'amount': Decimal('5.99')},
                {'id': 'EXP', 'name': 'Express',  'detail': '', 'amount': Decimal('14.50')},
            ],
        ):
            out = ship_services._bookvault_quote(
                self.rate,
                subtotal=Money(Decimal('20.00'), 'USD'),
                total_weight_kg=Decimal('0.5'),
            )
        self.assertIsNotNone(out)
        self.assertEqual(out.amount, Decimal('5.99'))

    def test_no_isbn_lines_returns_none(self):
        # Cart with no ISBN-13 SKU → BV service returns []; adapter → None.
        self._fake_cart(isbn=None)
        with patch(
            'plugins.installed.bookvault.services.get_shipping_rates',
            return_value=[],
        ):
            out = ship_services._bookvault_quote(
                self.rate,
                subtotal=Money(Decimal('20.00'), 'USD'),
                total_weight_kg=Decimal('0'),
            )
        self.assertIsNone(out)

    def test_no_cart_returns_none(self):
        # If the rate wasn't passed through list_available_rates, _cart
        # is missing — adapter MUST short-circuit, not crash.
        # (Don't attach _cart in setUp for this test.)
        out = ship_services._bookvault_quote(
            self.rate,
            subtotal=Money(Decimal('20.00'), 'USD'),
            total_weight_kg=Decimal('0'),
        )
        self.assertIsNone(out)
