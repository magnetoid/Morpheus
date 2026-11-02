"""The fraud score is shown where staff work: the order page and Linda.

fraud_rules wrote ``order.metadata['fraud_score']`` on every order and nothing
ever read it. Since v0.132.0 the order page shows a Fraud check card (through
``ORDER_DETAIL_PANELS``) and ``payments.order_risk`` answers Linda; an order the
check never scored shows neither.
"""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from djmoney.money import Money

from core.agents import agent_registry
from core.hooks import MorpheusEvents, hook_registry
from morpheus.core import ToolError
from plugins.installed.orders.models import Order
from plugins.installed.payments import risk


def _order(**metadata):
    return Order.objects.create(
        email='buyer@example.com',
        subtotal=Money(Decimal('20.00'), 'USD'),
        total=Money(Decimal('20.00'), 'USD'),
        metadata=metadata,
    )


SCORED = {
    'fraud_score': 65,
    'fraud_bucket': 'review',
    'fraud_flags': ['address_mismatch'],
}


class OrderPageTests(TestCase):
    def setUp(self):
        staff = get_user_model().objects.create_user(
            username='ops', email='ops@example.com', password='x', is_staff=True
        )
        self.client.force_login(staff)

    def test_a_scored_order_shows_its_fraud_check(self):
        order = _order(**SCORED)
        body = self.client.get(f'/dashboard/orders/{order.order_number}/').content.decode()
        self.assertIn('data-fraud-bucket="review"', body)
        self.assertIn('Fraud check', body)
        self.assertIn(risk.FLAG_LABELS['address_mismatch'], body)

    def test_an_unscored_order_has_no_card(self):
        order = _order()
        response = self.client.get(f'/dashboard/orders/{order.order_number}/')
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('data-fraud-bucket', response.content.decode())


class OrderRiskToolTests(TestCase):
    def setUp(self):
        self.tool = agent_registry.get_tool('payments.order_risk')

    def test_the_tool_is_registered_with_a_read_scope(self):
        self.assertIsNotNone(self.tool)
        self.assertEqual(list(self.tool.scopes), ['orders.read'])

    def test_it_reports_the_score_in_plain_words(self):
        order = _order(**SCORED)
        result = self.tool.invoke({'order_number': order.order_number})
        self.assertTrue(result.output['scored'])
        self.assertEqual(result.output['score'], 65)
        self.assertEqual(result.output['level'], 'Review')
        self.assertEqual(result.output['reasons'], [risk.FLAG_LABELS['address_mismatch']])

    def test_an_unscored_order_says_so(self):
        order = _order()
        result = self.tool.invoke({'order_number': order.order_number})
        self.assertEqual(result.output, {'order_number': order.order_number, 'scored': False})

    def test_an_unknown_order_is_an_error(self):
        with self.assertRaises(ToolError):
            self.tool.invoke({'order_number': 'NOPE-1'})


class OwnedHookTests(TestCase):
    """The score and the card stop when payments is off, like every contributed surface."""

    def _owners(self, event, handler):
        entries = [hook_registry._unpack(e) for e in hook_registry._handlers.get(event, [])]
        return {plugin for _p, h, _m, plugin in entries if h is handler}

    def test_payments_owns_its_hooks(self):
        self.assertEqual(
            self._owners(MorpheusEvents.ORDER_PLACED, risk.on_order_placed), {'payments'}
        )
        self.assertEqual(
            self._owners(MorpheusEvents.ORDER_DETAIL_PANELS, risk.order_panel), {'payments'}
        )

    def test_post_purchase_owns_its_hooks(self):
        from plugins.installed.post_purchase import handlers

        self.assertEqual(
            self._owners(MorpheusEvents.ORDER_PLACED, handlers.on_order_placed), {'post_purchase'}
        )
        self.assertEqual(
            self._owners(MorpheusEvents.ORDER_FULFILLED, handlers.on_order_fulfilled),
            {'post_purchase'},
        )
