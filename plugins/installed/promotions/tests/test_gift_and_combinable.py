"""A gift rule adds the free line to the order, and a promotion that doesn't
combine applies alone.

Until v0.150.0 a ``gift`` rule recorded a product id and nothing added it, and
every promotion stacked with every other and with any coupon.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase

from plugins.installed.marketing.models import Coupon
from plugins.installed.orders.services import OrderService

from ._fixtures import ADDRESS, applied_names, breakdown, cart, eur, product, promotion


class GiftLineTests(TestCase):
    def setUp(self):
        self.book = product('book', 50)
        self.bookmark = product('bookmark', 4)
        self.promo = promotion(
            'Free bookmark',
            {'kind': 'gift', 'product_id': str(self.bookmark.pk)},
            {'min_subtotal': 30},
        )

    def test_the_order_gets_the_gift_at_no_charge(self):
        order = OrderService.create_from_cart(
            cart((self.book, 50, 1)), 'buyer@example.com', ADDRESS, ADDRESS
        )
        lines = {i.product_id: i for i in order.items.all()}
        self.assertEqual(len(lines), 2)
        gift = lines[self.bookmark.pk]
        self.assertEqual(gift.unit_price.amount, Decimal('0'))
        self.assertEqual(gift.total_price.amount, Decimal('0'))
        self.assertEqual(order.total.amount, Decimal('50.00'))
        self.assertEqual(order.metadata['gift_lines'][0]['promotion'], 'Free bookmark')

    def test_no_gift_below_the_threshold(self):
        order = OrderService.create_from_cart(
            cart((self.bookmark, 4, 1)), 'buyer@example.com', ADDRESS, ADDRESS
        )
        self.assertEqual(order.items.count(), 1)

    def test_no_gift_when_the_product_is_not_on_sale(self):
        self.bookmark.status = 'draft'
        self.bookmark.save()
        self.assertNotIn('gift_lines', breakdown(cart((self.book, 50, 1)))['meta'])

    def test_no_gift_when_the_stock_app_says_it_is_out(self):
        out = {str(self.bookmark.pk): {'available': 0, 'low': True, 'out': True}}
        with patch(
            'morpheus.core.hook_registry.filter',
            side_effect=_answer_stock(out),
        ):
            result = breakdown(cart((self.book, 50, 1)))
        self.assertNotIn('gift_lines', result['meta'])
        self.assertEqual(applied_names(result), ['Free bookmark'])


class GiftVariantStockTests(TestCase):
    """The gift's own variant decides: a product with several needs one named,
    and that variant's stock must cover the cart's own units of it plus the
    gift, or the order's stock reservation refuses the whole checkout."""

    def setUp(self):
        from plugins.installed.catalog.models import ProductVariant
        from plugins.installed.inventory.models import StockLevel, Warehouse

        self.book = product('book', 50)
        self.tote = product('tote', 10)
        self.red = ProductVariant.objects.create(
            product=self.tote, name='Red', sku='TOTE-RED', price=eur(10)
        )
        self.blue = ProductVariant.objects.create(
            product=self.tote, name='Blue', sku='TOTE-BLUE', price=eur(10)
        )
        warehouse = Warehouse.objects.create(name='Main', code='MAIN')
        StockLevel.objects.create(variant=self.red, warehouse=warehouse, quantity=0)
        self.blue_stock = StockLevel.objects.create(
            variant=self.blue, warehouse=warehouse, quantity=5
        )

    def _gift(self, variant=None):
        action = {'kind': 'gift', 'product_id': str(self.tote.pk)}
        if variant is not None:
            action['variant_id'] = str(variant.pk)
        promotion('Free tote', action)

    def _order(self, c):
        return OrderService.create_from_cart(c, 'buyer@example.com', ADDRESS, ADDRESS)

    def _gifts(self, order):
        return [i for i in order.items.all() if i.unit_price.amount == 0]

    def test_no_gift_when_the_product_has_several_variants_and_the_rule_names_none(self):
        from plugins.installed.inventory.models import StockLevel

        # Both in stock, so only the missing variant can refuse the gift.
        StockLevel.objects.filter(variant=self.red).update(quantity=5)
        self._gift()
        order = self._order(cart((self.book, 50, 1)))
        self.assertEqual(self._gifts(order), [])

    def test_the_named_variant_is_given_and_reserved(self):
        self._gift(self.blue)
        order = self._order(cart((self.book, 50, 1)))
        [gift] = self._gifts(order)
        self.assertEqual(gift.variant, self.blue)
        self.blue_stock.refresh_from_db()
        self.assertEqual(self.blue_stock.reserved_quantity, 1)

    def test_an_out_of_stock_variant_is_not_given_and_the_order_goes_through(self):
        # Red has none, blue has five: the product's summed stock says in stock.
        self._gift(self.red)
        order = self._order(cart((self.book, 50, 1)))
        self.assertEqual(self._gifts(order), [])
        self.assertEqual(order.items.count(), 1)

    def test_the_carts_own_units_of_the_variant_count(self):
        from plugins.installed.orders.models import CartItem

        self.blue_stock.quantity = 1
        self.blue_stock.save()
        self._gift(self.blue)
        c = cart((self.book, 50, 1))
        CartItem.objects.create(
            cart=c, product=self.tote, variant=self.blue, quantity=1, unit_price=eur(10)
        )
        order = self._order(c)
        self.assertEqual(self._gifts(order), [])
        self.assertEqual(order.items.count(), 2)


def _answer_stock(answer):
    """Answer PRODUCT_STOCK_SUMMARY with ``answer``, pass every other filter on."""
    from morpheus.core import MorpheusEvents, hook_registry

    real = hook_registry.__class__.filter.__get__(hook_registry)

    def fake(event, value=None, **kwargs):
        if event == MorpheusEvents.PRODUCT_STOCK_SUMMARY:
            return answer
        return real(event, value=value, **kwargs)

    return fake


class CombinableTests(TestCase):
    def setUp(self):
        self.book = product('book', 100)

    def test_promotions_stack_by_default(self):
        promotion('Ten', {'kind': 'percent_off', 'value': 10}, priority=1)
        promotion('Five', {'kind': 'fixed_off', 'value': 5}, priority=2)
        result = breakdown(cart((self.book, 100, 1)))
        self.assertEqual(result['discount'].amount, Decimal('15.00'))

    def test_an_exclusive_promotion_after_another_is_skipped(self):
        promotion('Ten', {'kind': 'percent_off', 'value': 10}, priority=1)
        promotion('Alone', {'kind': 'fixed_off', 'value': 30}, priority=2, combinable=False)
        self.assertEqual(applied_names(breakdown(cart((self.book, 100, 1)))), ['Ten'])

    def test_an_exclusive_promotion_first_stops_the_rest(self):
        promotion('Alone', {'kind': 'fixed_off', 'value': 30}, priority=1, combinable=False)
        promotion('Ten', {'kind': 'percent_off', 'value': 10}, priority=2)
        result = breakdown(cart((self.book, 100, 1)))
        self.assertEqual(applied_names(result), ['Alone'])
        self.assertEqual(result['discount'].amount, Decimal('30.00'))

    def test_a_typed_code_wins_over_an_exclusive_promotion(self):
        promotion('Alone', {'kind': 'fixed_off', 'value': 30}, combinable=False)
        code = Coupon.objects.create(
            code='TEN', name='Ten', discount_type='percentage', discount_value=Decimal('10')
        )
        result = breakdown(cart((self.book, 100, 1), coupon=code))
        self.assertEqual(applied_names(result), [])
        self.assertEqual(result['discount'].amount, Decimal('10.00'))

    def test_the_promotion_a_code_unlocks_still_applies_with_it(self):
        promotion(
            'Code extra', {'kind': 'fixed_off', 'value': 5}, combinable=False, requires_coupon='TEN'
        )
        code = Coupon.objects.create(
            code='TEN', name='Ten', discount_type='percentage', discount_value=Decimal('10')
        )
        result = breakdown(cart((self.book, 100, 1), coupon=code))
        self.assertEqual(applied_names(result), ['Code extra'])
        self.assertEqual(result['discount'].amount, Decimal('15.00'))

    def test_discounts_never_exceed_the_cart(self):
        promotion('Big', {'kind': 'fixed_off', 'value': 80}, priority=1)
        promotion('Bigger', {'kind': 'fixed_off', 'value': 80}, priority=2)
        result = breakdown(cart((self.book, 100, 1)))
        self.assertEqual(result['discount'].amount, Decimal('100.00'))
        self.assertEqual(result['total'].amount, Decimal('0.00'))


class BuyXGetYRuleTests(TestCase):
    def test_a_bogo_rule_at_half_price(self):
        dear, cheap = product('dear', 30), product('cheap', 10)
        promotion('B2G1 half', {'kind': 'bogo', 'buy_qty': 2, 'free_qty': 1, 'percent': 50})
        result = breakdown(cart((dear, 30, 2), (cheap, 10, 1)))
        self.assertEqual(result['discount'].amount, Decimal('5.00'))
