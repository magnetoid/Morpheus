"""Refund + Return tests."""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from djmoney.money import Money

from core.agents import agent_registry
from plugins.installed.catalog.models import Product
from plugins.installed.orders.models import Order, OrderItem
from plugins.installed.orders.refunds import RefundService, ReturnService

User = get_user_model()


def _setup_order(amount='25', qty=2):
    user = User.objects.create_user(username='c', email='c@example.com', password='x')
    p = Product.objects.create(
        name='Book',
        slug='book',
        sku='B',
        price=Money(Decimal(amount), 'USD'),
        status='active',
    )
    order = Order.objects.create(
        customer=user,
        email='c@example.com',
        subtotal=Money(Decimal(amount) * qty, 'USD'),
        total=Money(Decimal(amount) * qty, 'USD'),
    )
    item = OrderItem.objects.create(
        order=order,
        product=p,
        product_name=p.name,
        sku=p.sku,
        quantity=qty,
        unit_price=p.price,
        total_price=p.price * qty,
    )
    return order, item


def _succeeded_stripe_tx(order):
    """Give the order a successful Stripe transaction so a gateway refund
    has something to refund against."""
    from plugins.installed.payments.models import PaymentTransaction

    return PaymentTransaction.objects.create(
        order=order,
        amount=order.total,
        status=PaymentTransaction.Status.SUCCEEDED,
        provider='stripe',
        provider_transaction_id='pi_test_123',
    )


class RefundServiceTests(TestCase):
    def test_gateway_backed_refund_moves_money_and_marks_processed(self):
        # The returns/agent path must issue a REAL gateway refund. It used to
        # short-circuit to is_processed=True without ever calling the provider
        # (phantom refund: customer emailed "refunded" while no money moved).
        from unittest.mock import patch

        from plugins.installed.payments.gateways.stripe_gateway import StripeGateway

        order, _ = _setup_order()
        _succeeded_stripe_tx(order)
        with patch.object(StripeGateway, 'refund', return_value={'success': True}) as m:
            refund = RefundService.process(order=order, amount=Money(Decimal('10'), 'USD'))
        self.assertTrue(m.called)
        refund.refresh_from_db()
        self.assertTrue(refund.is_processed)

    def test_no_transaction_leaves_refund_unprocessed(self):
        # A COD/manual/unpaid order has no gateway transaction — the refund row
        # is recorded but NOT marked processed, and no "refunded" email fires.
        order, _ = _setup_order()
        refund = RefundService.process(order=order, amount=Money(Decimal('10'), 'USD'))
        refund.refresh_from_db()
        self.assertFalse(refund.is_processed)

    def test_over_refund_is_rejected(self):
        order, _ = _setup_order(amount='25', qty=2)  # total = 50
        RefundService.process(
            order=order, amount=Money(Decimal('50'), 'USD')
        )  # unprocessed (no tx)
        # Even without a gateway tx, a refund exceeding the order total must be
        # refused outright (the returns/agent paths used to bypass any cap).
        with self.assertRaises(ValueError):
            RefundService.process(order=order, amount=Money(Decimal('60'), 'USD'))

    def test_process_is_idempotent(self):
        order, _ = _setup_order()
        r1 = RefundService.process(order=order, amount=Money(Decimal('5'), 'USD'))
        r2 = RefundService.process(order=order, amount=Money(Decimal('5'), 'USD'))
        self.assertEqual(r1.id, r2.id)

    def test_gateway_success_fires_payment_refunded_once(self):
        # PAYMENT_REFUNDED (refund email / affiliate clawback / pixel) fires
        # exactly once, and ONLY after the gateway confirmed the refund.
        from unittest.mock import patch

        from core.hooks import MorpheusEvents, hook_registry
        from plugins.installed.payments.gateways.stripe_gateway import StripeGateway

        seen = []

        def _handler(refund=None, order=None, **kwargs):
            seen.append((refund, order))

        hook_registry.register(MorpheusEvents.PAYMENT_REFUNDED, _handler, plugin=None)
        try:
            order, _ = _setup_order()
            _succeeded_stripe_tx(order)
            with patch.object(StripeGateway, 'refund', return_value={'success': True}):
                RefundService.process(order=order, amount=Money(Decimal('5'), 'USD'))
        finally:
            hook_registry.unregister(MorpheusEvents.PAYMENT_REFUNDED, _handler)
        self.assertEqual(len(seen), 1)
        self.assertEqual(seen[0][1].pk, order.pk)


class ReturnRequestTests(TestCase):
    def test_create_assigns_rma_number(self):
        order, item = _setup_order()
        rr = ReturnService.create_request(
            order=order,
            items=[{'order_item_id': str(item.id), 'quantity': 1}],
            reason='defective',
        )
        self.assertTrue(rr.rma_number.startswith('RMA-'))
        self.assertEqual(rr.state, 'requested')

    def test_approve_computes_refund_amount(self):
        order, item = _setup_order(amount='30', qty=2)
        rr = ReturnService.create_request(
            order=order,
            items=[{'order_item_id': str(item.id), 'quantity': 2}],
        )
        ReturnService.approve(rr)
        rr.refresh_from_db()
        self.assertEqual(rr.state, 'approved')
        self.assertEqual(rr.refund_amount.amount, Decimal('60.00'))

    def test_full_flow_to_refunded(self):
        order, item = _setup_order(amount='20', qty=1)
        rr = ReturnService.create_request(
            order=order,
            items=[{'order_item_id': str(item.id), 'quantity': 1}],
        )
        ReturnService.approve(rr)
        ReturnService.mark_received_and_refund(rr)
        rr.refresh_from_db()
        self.assertEqual(rr.state, 'refunded')
        self.assertIsNotNone(rr.refund_id)


class RefundAgentToolsTests(TestCase):
    def test_tools_registered(self):
        names = {t.name for t in agent_registry.platform_tools()}
        self.assertIn('orders.refund', names)
        self.assertIn('returns.list', names)
        self.assertIn('returns.approve', names)
