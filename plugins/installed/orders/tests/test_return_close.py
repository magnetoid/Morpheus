"""Closing a return by refund, store credit or exchange (C4, v0.188.0)."""

from __future__ import annotations

from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from djmoney.money import Money

from core.hooks import MorpheusEvents, hook_registry
from plugins.installed.catalog.models import Product, ProductVariant
from plugins.installed.orders.models import Order, OrderItem, Refund
from plugins.installed.orders.refunds import ReturnRequest, ReturnService


def _usd(n):
    return Money(n, 'USD')


class _Base(TestCase):
    def setUp(self):
        self.book = Product.objects.create(
            name='Zephyr Atlas', slug='zephyr-atlas', sku='ZA', price=10, product_type='variable'
        )
        self.paperback = ProductVariant.objects.create(
            product=self.book, name='Paperback', sku='ZA-PB', price=_usd(10)
        )
        self.hardback = ProductVariant.objects.create(
            product=self.book, name='Hardback', sku='ZA-HB', price=_usd(10)
        )
        self.pocket = ProductVariant.objects.create(
            product=self.book, name='Pocket', sku='ZA-PO', price=_usd(7)
        )
        self.deluxe = ProductVariant.objects.create(
            product=self.book, name='Deluxe', sku='ZA-DX', price=_usd(30)
        )
        self.customer = get_user_model().objects.create_user(
            username='quillon', email='quillon@example.com', password='x'
        )
        self.order = Order.objects.create(
            customer=self.customer,
            email='quillon@example.com',
            subtotal=_usd(10),
            total=_usd(10),
            payment_status='paid',
            payment_gateway='manual',
            shipping_address={'line1': '1 Zephyr Way', 'country': 'US'},
        )
        self.item = OrderItem.objects.create(
            order=self.order,
            product=self.book,
            variant=self.paperback,
            product_name='Zephyr Atlas',
            variant_name='Paperback',
            quantity=1,
            unit_price=_usd(10),
            total_price=_usd(10),
        )
        self.rr = ReturnRequest.objects.create(
            order=self.order,
            state='approved',
            items=[{'order_item_id': str(self.item.pk), 'quantity': 1}],
        )

    def exchange(self, variant):
        from plugins.installed.orders.exchange import ExchangeLine

        return [
            ExchangeLine(order_item_id=str(self.item.pk), variant_id=str(variant.pk), quantity=1)
        ]

    def close(self, outcome, **kw):
        # No gateway answers in tests: a money refund is recorded and left for
        # reconciliation, which is all these tests read.
        return ReturnService.close(self.rr, outcome=outcome, **kw)

    def exchange_orders(self):
        return Order.objects.filter(metadata__exchange_of=self.rr.rma_number)


class CloseRefundTests(_Base):
    def test_close_refund_matches_todays_refund(self):
        rr = self.close('refund')
        self.assertEqual(rr.state, 'refunded')
        self.assertEqual(rr.refund.amount, _usd(10))

    def test_close_store_credit_takes_off_the_fee(self):
        from plugins.installed.orders import store_credit

        self.close('store_credit', fee=_usd(3))
        self.assertEqual(store_credit.balance(self.customer).amount, 7)

    def test_fee_never_makes_a_refund_negative(self):
        rr = self.close('refund', fee=_usd(50))
        self.assertEqual(rr.state, 'refunded')
        self.assertFalse(Refund.objects.filter(order=self.order, amount__gt=0).exists())

    def test_close_twice_is_refused(self):
        self.close('refund')
        with self.assertRaises(ValueError):
            self.close('refund')


class CloseExchangeTests(_Base):
    def test_equal_price_exchange_is_a_paid_zero_order_linked_to_the_return(self):
        self.close('exchange', exchange=self.exchange(self.hardback))
        new = self.exchange_orders().get()
        self.assertEqual(new.total, _usd(0))
        self.assertEqual(new.payment_status, 'paid')
        self.assertEqual(new.metadata['exchange_of'], self.rr.rma_number)
        self.assertEqual(new.items.get().variant_id, self.hardback.pk)
        self.assertEqual(new.shipping_address, self.order.shipping_address)
        self.assertEqual(new.customer_id, self.customer.pk)

    def test_exchange_order_fires_no_placed_or_paid_event(self):
        seen = []
        for event in (MorpheusEvents.ORDER_PLACED, MorpheusEvents.ORDER_PAID):
            saved = list(hook_registry._handlers.get(event, []))
            self.addCleanup(hook_registry._handlers.__setitem__, event, saved)
            hook_registry.register(event, lambda e=event, **kw: seen.append(e), priority=1)
        with self.captureOnCommitCallbacks(execute=True):
            self.close('exchange', exchange=self.exchange(self.hardback))
        self.assertEqual(seen, [])

    def test_cheaper_edition_refunds_the_difference(self):
        self.close('exchange', exchange=self.exchange(self.pocket))
        self.assertEqual(self.exchange_orders().get().total, _usd(0))
        self.assertEqual(Refund.objects.get(order=self.order).amount, _usd(3))

    def test_fee_comes_off_the_difference_first_then_goes_on_the_order(self):
        self.close('exchange', exchange=self.exchange(self.pocket), fee=_usd(5))
        self.assertFalse(Refund.objects.filter(order=self.order).exists())
        new = self.exchange_orders().get()
        self.assertEqual(new.total, _usd(2))
        self.assertEqual(new.payment_status, 'unpaid')
        self.assertEqual(new.shipping_method, 'Exchange fee')

    def test_sold_out_edition_is_refunded_instead(self):
        with mock.patch(
            'plugins.installed.orders.exchange.units_available',
            return_value={str(self.hardback.pk): 0},
        ):
            rr = self.close('exchange', exchange=self.exchange(self.hardback))
        self.assertFalse(self.exchange_orders().exists())
        self.assertEqual(rr.refund.amount, _usd(10))

    def test_dearer_edition_is_refused(self):
        rr = self.close('exchange', exchange=self.exchange(self.deluxe))
        self.assertFalse(self.exchange_orders().exists())
        self.assertEqual(rr.refund.amount, _usd(10))

    def test_return_refunded_fires_once_with_the_outcome(self):
        calls = []
        saved = list(hook_registry._handlers.get('return.refunded', []))
        self.addCleanup(hook_registry._handlers.__setitem__, 'return.refunded', saved)
        hook_registry.register('return.refunded', lambda **kw: calls.append(kw), priority=1)
        self.close('exchange', exchange=self.exchange(self.hardback))
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]['outcome'], 'exchange')
        self.assertEqual(calls[0]['exchange_order'], self.exchange_orders().get())
        self.assertEqual(calls[0]['unmade'], [])

    def test_unmade_lines_reach_webhooks_as_plain_data(self):
        calls = []
        saved = list(hook_registry._handlers.get('return.refunded', []))
        self.addCleanup(hook_registry._handlers.__setitem__, 'return.refunded', saved)
        hook_registry.register('return.refunded', lambda **kw: calls.append(kw), priority=1)
        self.close('exchange', exchange=self.exchange(self.deluxe))
        expected = [
            {'order_item_id': str(self.item.pk), 'variant_id': str(self.deluxe.pk), 'quantity': 1}
        ]
        self.assertEqual(calls[0]['unmade'], expected)
        self.assertEqual(
            hook_registry._serialize_payload({'unmade': calls[0]['unmade']}), {'unmade': expected}
        )


class ReviewFixTests(_Base):
    """The final review's findings on closing an exchange (C4, v0.188.0)."""

    def test_a_discounted_order_still_exchanges_for_an_equal_edition(self):
        Order.objects.filter(pk=self.order.pk).update(discount_total=_usd(1), total=_usd(9))
        self.rr.refresh_from_db()
        self.close('exchange', exchange=self.exchange(self.hardback))
        new = self.exchange_orders().get()
        self.assertEqual(new.items.get().variant_id, self.hardback.pk)
        self.assertFalse(Refund.objects.filter(order=self.order).exists())

    def test_exchange_order_money_is_in_the_order_currency(self):
        Order.objects.filter(pk=self.order.pk).update(
            subtotal=Money(10, 'EUR'), total=Money(10, 'EUR')
        )
        self.rr.refresh_from_db()
        self.close('exchange', exchange=self.exchange(self.hardback))
        new = self.exchange_orders().get()
        for field in ('subtotal', 'shipping_total', 'tax_total', 'discount_total', 'total'):
            with self.subTest(field=field):
                self.assertEqual(str(getattr(new, field).currency), 'EUR')

    def cancel_unpaid_exchange(self):
        new = self.exchange_orders().get()
        with self.captureOnCommitCallbacks(execute=True):
            new.cancel(reason='Not paid in time')
            new.save()

    def test_unpaid_exchange_is_refunded_even_with_the_portal_off(self):
        from plugins.registry import app_registry

        self.close('exchange', exchange=self.exchange(self.hardback), fee=_usd(5))
        app_registry.deactivate('returns_portal')
        self.addCleanup(app_registry.activate, 'returns_portal')
        self.cancel_unpaid_exchange()
        self.assertEqual(Refund.objects.get(order=self.order).amount, _usd(10))

    def test_unpaid_exchange_refund_counts_an_earlier_processed_refund_once(self):
        second = OrderItem.objects.create(
            order=self.order,
            product=self.book,
            variant=self.paperback,
            product_name='Zephyr Atlas',
            variant_name='Paperback',
            quantity=1,
            unit_price=_usd(10),
            total_price=_usd(10),
        )
        Order.objects.filter(pk=self.order.pk).update(subtotal=_usd(20), total=_usd(20))
        ReturnRequest.objects.filter(pk=self.rr.pk).update(
            items=[
                {'order_item_id': str(self.item.pk), 'quantity': 1},
                {'order_item_id': str(second.pk), 'quantity': 1},
            ]
        )
        self.rr.refresh_from_db()
        from plugins.installed.orders.exchange import ExchangeLine

        lines = [
            *self.exchange(self.hardback),
            ExchangeLine(order_item_id=str(second.pk), variant_id=str(self.deluxe.pk)),
        ]
        self.close('exchange', exchange=lines, fee=_usd(5))
        Refund.objects.filter(order=self.order).update(is_processed=True)  # as a gateway would
        self.cancel_unpaid_exchange()
        amounts = sorted(r.amount.amount for r in Refund.objects.filter(order=self.order))
        self.assertEqual(amounts, [10, 10])
