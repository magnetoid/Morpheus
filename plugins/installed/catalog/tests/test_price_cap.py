"""Max price-change % guardrail on products.update_price.

The per-action cap (Settings → Agent guardrails) refuses an agent price edit
whose magnitude exceeds it. 0/unset = no cap; a change from an unset/zero base
is undefined and allowed (the cap bounds *changes*, not first prices).
"""

from __future__ import annotations

from decimal import Decimal
from unittest import mock

from django.test import TestCase
from djmoney.money import Money

from core.agents.tools import ToolError
from plugins.installed.catalog.agent_tools import (
    _enforce_price_delta,
    products_update_price_tool,
)
from plugins.installed.catalog.models import Product


class EnforcePriceDeltaUnitTests(TestCase):
    def test_over_cap_raises(self):
        with self.assertRaises(ToolError) as ctx:
            _enforce_price_delta(Decimal('10'), Decimal('15'), 20)  # +50% > 20%
        self.assertIn('exceeds', str(ctx.exception))

    def test_under_cap_allowed(self):
        _enforce_price_delta(Decimal('10'), Decimal('11'), 20)  # +10% ≤ 20% → no raise

    def test_zero_cap_is_no_cap(self):
        _enforce_price_delta(Decimal('10'), Decimal('1000'), 0)  # cap off → allowed

    def test_unset_or_zero_base_is_allowed(self):
        _enforce_price_delta(None, Decimal('50'), 20)  # first price
        _enforce_price_delta(Decimal('0'), Decimal('50'), 20)  # zero base → undefined %


class PriceToolCapTests(TestCase):
    def _product(self, price='10'):
        return Product.objects.create(
            name='Book', slug='book', sku='B', price=Money(Decimal(price), 'USD'), status='active'
        )

    def test_price_tool_refuses_over_cap_change(self):
        p = self._product('10')
        with (
            mock.patch(
                'plugins.installed.catalog.agent_tools.max_price_change_pct', return_value=20
            ),
            self.assertRaises(ToolError) as ctx,
        ):
            products_update_price_tool.invoke(
                {'id': str(p.id), 'price': '100', 'confirmed': True}  # +900%
            )
        self.assertIn('exceeds', str(ctx.exception))
        p.refresh_from_db()
        self.assertEqual(p.price.amount, Decimal('10'))  # unchanged

    def test_price_tool_allows_under_cap_change(self):
        p = self._product('10')
        with mock.patch(
            'plugins.installed.catalog.agent_tools.max_price_change_pct', return_value=20
        ):
            products_update_price_tool.invoke(
                {'id': str(p.id), 'price': '11', 'confirmed': True}  # +10%
            )
        p.refresh_from_db()
        self.assertEqual(p.price.amount, Decimal('11'))
