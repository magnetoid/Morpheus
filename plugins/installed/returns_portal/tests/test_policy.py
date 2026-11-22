"""What a return may become, and what it costs (C4, v0.188.0)."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase
from djmoney.money import Money

from core.hooks import MorpheusEvents, hook_registry
from plugins.installed.catalog.models import Product, ProductVariant
from plugins.installed.orders.models import Order, OrderItem
from plugins.installed.orders.refunds import ReturnRequest
from plugins.testing import set_app_settings


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
        self.retired = ProductVariant.objects.create(
            product=self.book, name='Retired', sku='ZA-RT', price=_usd(8), is_active=False
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
        )
        self.item = OrderItem.objects.create(
            order=self.order,
            product=self.book,
            variant=self.paperback,
            product_name='Zephyr Atlas',
            quantity=1,
            unit_price=_usd(10),
            total_price=_usd(10),
        )

    def settings_on(self, **values):
        set_app_settings(self, 'returns_portal', **values)


class OfferedOutcomeTests(_Base):
    def test_refund_is_always_offered(self):
        from plugins.installed.returns_portal.policy import offered_outcomes

        self.assertEqual(offered_outcomes(self.order, signed_in=True), ['refund'])

    def test_store_credit_needs_the_switch_and_an_account(self):
        from plugins.installed.returns_portal.policy import offered_outcomes

        self.settings_on(refund_store_credit=True)
        self.assertIn('store_credit', offered_outcomes(self.order, signed_in=True))
        self.assertNotIn('store_credit', offered_outcomes(self.order, signed_in=False))
        self.order.customer = None
        self.assertNotIn('store_credit', offered_outcomes(self.order, signed_in=True))

    def test_exchange_needs_the_switch(self):
        from plugins.installed.returns_portal.policy import offered_outcomes

        self.assertNotIn('exchange', offered_outcomes(self.order, signed_in=True))
        self.settings_on(refund_exchange=True)
        self.assertIn('exchange', offered_outcomes(self.order, signed_in=True))

    def test_editions_are_same_product_for_sale_and_not_dearer(self):
        from plugins.installed.returns_portal.policy import exchange_editions

        found = {v.sku for v in exchange_editions(self.item)}
        self.assertEqual(found, {'ZA-HB', 'ZA-PO'})

    def test_a_discount_or_tender_does_not_hide_an_equal_edition(self):
        from plugins.installed.returns_portal.policy import exchange_editions

        Order.objects.filter(pk=self.order.pk).update(discount_total=_usd(5), total=_usd(5))
        self.item.refresh_from_db()
        self.assertIn('ZA-HB', {v.sku for v in exchange_editions(self.item)})


class FeeTests(_Base):
    def test_exchange_fee_modes(self):
        from plugins.installed.returns_portal.policy import exchange_fee, return_fee

        self.assertEqual(exchange_fee(self.order), _usd(0))
        cases = [
            ({'exchange_fee': 'free'}, 0),
            (
                {
                    'exchange_fee': 'same_as_return',
                    'return_fees': 'fixed_fee',
                    'return_shipping_fee': 4,
                },
                4,
            ),
            (
                {'exchange_fee': 'same_as_return', 'return_fees': 'free', 'return_shipping_fee': 4},
                0,
            ),
            ({'exchange_fee': 'fixed', 'exchange_fee_amount': 6}, 6),
        ]
        for values, expected in cases:
            with self.subTest(values=values):
                self.settings_on(**values)
                self.assertEqual(exchange_fee(self.order), _usd(expected))
        self.settings_on(return_fees='fixed_fee', return_shipping_fee=4)
        self.assertEqual(return_fee(self.order), _usd(4))


class ResolutionHookTests(_Base):
    def setUp(self):
        super().setUp()
        self.rr = ReturnRequest.objects.create(
            order=self.order, items=[{'order_item_id': str(self.item.pk), 'quantity': 1}]
        )

    def resolution(self):
        return hook_registry.filter(MorpheusEvents.RETURN_RESOLUTION, None, return_request=self.rr)

    def test_resolution_hook_answers_from_the_portal_row(self):
        from plugins.installed.returns_portal.models import ReturnResolution

        self.settings_on(exchange_fee='fixed', exchange_fee_amount=6)
        ReturnResolution.objects.create(
            request=self.rr,
            resolution='exchange',
            exchange_choices=[
                {'order_item_id': str(self.item.pk), 'exchange_variant_id': str(self.hardback.pk)}
            ],
        )
        answer = self.resolution()
        self.assertEqual(answer['outcome'], 'exchange')
        self.assertEqual(answer['fee'], _usd(6))
        line = answer['exchange'][0]
        self.assertEqual(
            (line.order_item_id, line.variant_id, line.quantity),
            (str(self.item.pk), str(self.hardback.pk), 1),
        )

    def test_resolution_hook_is_none_without_a_row(self):
        self.assertIsNone(self.resolution())
