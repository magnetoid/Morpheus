"""Anonymous purchase attribution (autopilot-plan follow-up): checkout stamps
the morph_visitor cookie into Order.metadata['visitor_id']; the ORDER_PLACED
handler resolves it to the `v:<cookie>` assignment and bumps the conversion.
Before this, anonymous conversions were silently dropped (only `u:` customers
attributed) — the experiments/bandit loop never saw guest purchases."""

# ruff: noqa: PLC0415
from __future__ import annotations

from decimal import Decimal

from django.test import TestCase
from djmoney.money import Money

from plugins.installed.catalog.models import Product, ProductVariant
from plugins.installed.experiments.models import Assignment, Experiment, Exposure
from plugins.installed.experiments.services import VISITOR_COOKIE
from plugins.installed.inventory.models import StockLevel, Warehouse
from plugins.installed.orders.services import CartService, OrderService

_ADDR = {'first_name': 'V', 'last_name': 'H', 'line1': '1 Main', 'country': 'US'}


class VisitorCookieContractTests(TestCase):
    def test_visitor_cookie_contract(self):
        # Checkout (orders/graphql/mutations.py + agentic_checkout/views.py)
        # reads this cookie by its literal name — renaming it silently kills
        # anonymous attribution, so the name is frozen here.
        self.assertEqual(VISITOR_COOKIE, 'morph_visitor')


class AnonymousOrderAttributionTests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(
            name='Attr Book',
            slug='attr-book',
            sku='AT1',
            price=Money(Decimal('20.00'), 'USD'),
            status='active',
        )
        self.variant = ProductVariant.objects.create(
            product=self.product,
            name='Paperback',
            sku='AT1-PB',
            price=Money(Decimal('20.00'), 'USD'),
        )
        wh = Warehouse.objects.create(name='Main', code='MAIN', is_default=True)
        StockLevel.objects.create(
            variant=self.variant, warehouse=wh, quantity=10, reserved_quantity=0
        )
        self.exp = Experiment.objects.create(
            key='hero-copy',
            status='running',
            goal='purchase',
            variants=[{'name': 'control', 'weight': 1}, {'name': 'b', 'weight': 1}],
        )
        Assignment.objects.create(experiment=self.exp, visitor_id='v:abc', variant='b')

    def _checkout(self, session_key, *, visitor_id=''):
        cart = CartService.get_or_create_cart(session_key=session_key)
        CartService.add_item(
            cart, str(self.product.id), quantity=1, variant_id=str(self.variant.id)
        )
        return OrderService.create_from_cart(
            cart, 'guest@example.com', _ADDR, _ADDR, visitor_id=visitor_id
        )

    def _conversions(self, variant):
        row = Exposure.objects.filter(experiment=self.exp, variant=variant).first()
        return row.conversions if row else 0

    def test_stamped_visitor_converts_v_assignment_end_to_end(self):
        # create_from_cart fires ORDER_PLACED → experiments' subscriber reads
        # metadata['visitor_id'] and credits the v:abc assignment's variant.
        self._checkout('s-attr-1', visitor_id='abc')
        self.assertEqual(self._conversions('b'), 1)

    def test_unstamped_anonymous_order_records_nothing(self):
        self._checkout('s-attr-2')
        self.assertEqual(self._conversions('b'), 0)
        self.assertEqual(self._conversions('control'), 0)
