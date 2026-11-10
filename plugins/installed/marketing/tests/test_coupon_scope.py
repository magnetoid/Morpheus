"""A coupon discounts only the lines it names.

Until v0.150.0 nothing read ``applicable_products``, ``applicable_categories``,
``applicable_collections`` or ``exclude_sale_items``: a code meant for one shelf
took its percentage off the whole cart, and the code box accepted it for a cart
it could not apply to. A Buy X get Y code took nothing off at all, and a free
shipping code was never counted against its usage limit.
"""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from plugins.installed.catalog.models import Collection
from plugins.installed.marketing.models import Coupon
from plugins.installed.orders.services import OrderService
from plugins.installed.promotions.tests._fixtures import (
    ADDRESS,
    breakdown,
    cart,
    category,
    eur,
    product,
)


def _coupon(code='SAVE10', discount_type='percentage', value=10, **kwargs):
    return Coupon.objects.create(
        code=code,
        name=code,
        discount_type=discount_type,
        discount_value=Decimal(str(value)),
        **kwargs,
    )


class CouponScopeTests(TestCase):
    def setUp(self):
        self.fiction = category('fiction')
        self.crime = category('crime', parent=self.fiction)
        self.novel = product('novel', 40, category=self.crime)
        self.mug = product('mug', 60)

    def test_an_unscoped_coupon_discounts_the_whole_cart(self):
        result = breakdown(cart((self.novel, 40, 1), (self.mug, 60, 1), coupon=_coupon()))
        self.assertEqual(result['discount'].amount, Decimal('10.00'))

    def test_a_category_coupon_discounts_only_the_category_and_below(self):
        coupon = _coupon()
        coupon.applicable_categories.add(self.fiction)
        result = breakdown(cart((self.novel, 40, 1), (self.mug, 60, 1), coupon=coupon))
        self.assertEqual(result['discount'].amount, Decimal('4.00'))

    def test_a_product_coupon(self):
        coupon = _coupon()
        coupon.applicable_products.add(self.mug)
        result = breakdown(cart((self.novel, 40, 1), (self.mug, 60, 1), coupon=coupon))
        self.assertEqual(result['discount'].amount, Decimal('6.00'))

    def test_a_collection_coupon(self):
        gifts = Collection.objects.create(name='Gifts', slug='gifts')
        self.mug.collections.add(gifts)
        coupon = _coupon()
        coupon.applicable_collections.add(gifts)
        result = breakdown(cart((self.novel, 40, 1), (self.mug, 60, 1), coupon=coupon))
        self.assertEqual(result['discount'].amount, Decimal('6.00'))

    def test_a_fixed_amount_is_capped_at_the_lines_it_covers(self):
        coupon = _coupon(discount_type='fixed_amount', value=50)
        coupon.applicable_products.add(self.novel)
        result = breakdown(cart((self.novel, 40, 1), (self.mug, 60, 1), coupon=coupon))
        self.assertEqual(result['discount'].amount, Decimal('40.00'))

    def test_sale_items_are_skipped_when_the_coupon_says_so(self):
        self.mug.compare_at_price = eur(80)
        self.mug.save()
        result = breakdown(
            cart((self.novel, 40, 1), (self.mug, 60, 1), coupon=_coupon(exclude_sale_items=True))
        )
        self.assertEqual(result['discount'].amount, Decimal('4.00'))

    def test_a_scoped_coupon_on_a_cart_it_does_not_cover_takes_nothing_off(self):
        coupon = _coupon()
        coupon.applicable_products.add(self.novel)
        result = breakdown(cart((self.mug, 60, 1), coupon=coupon))
        self.assertEqual(result['discount'].amount, Decimal('0.00'))
        self.assertNotIn('coupon', result['meta'])


class BuyXGetYCouponTests(TestCase):
    def setUp(self):
        self.cheap = product('cheap', 10)
        self.dear = product('dear', 30)

    def test_buy_two_get_one_free_frees_the_cheapest_unit(self):
        coupon = _coupon('B2G1', 'buy_x_get_y', 100, buy_quantity=2, get_quantity=1)
        result = breakdown(cart((self.dear, 30, 2), (self.cheap, 10, 1), coupon=coupon))
        self.assertEqual(result['discount'].amount, Decimal('10.00'))

    def test_a_percent_off_the_y_items(self):
        coupon = _coupon('B1G1HALF', 'buy_x_get_y', 50, buy_quantity=1, get_quantity=1)
        result = breakdown(cart((self.dear, 30, 2), coupon=coupon))
        self.assertEqual(result['discount'].amount, Decimal('15.00'))

    def test_too_few_units_take_nothing_off(self):
        coupon = _coupon('B2G1', 'buy_x_get_y', 100, buy_quantity=2, get_quantity=1)
        self.assertEqual(
            breakdown(cart((self.dear, 30, 2), coupon=coupon))['discount'].amount, Decimal('0.00')
        )

    def test_only_eligible_units_count(self):
        coupon = _coupon('B1G1', 'buy_x_get_y', 0, buy_quantity=1, get_quantity=1)
        coupon.applicable_products.add(self.dear)
        result = breakdown(cart((self.dear, 30, 2), (self.cheap, 10, 2), coupon=coupon))
        self.assertEqual(result['discount'].amount, Decimal('30.00'))


class CodeBoxTests(TestCase):
    """The GraphQL ``applyCoupon`` behind the storefront's code box."""

    def setUp(self):
        self.novel = product('novel', 40)
        self.mug = product('mug', 60)

    def _apply(self, code, *lines):
        c = cart(*lines)
        c.session_key = ''  # an anonymous cart the caller's session may claim
        c.save(update_fields=['session_key'])
        query = (
            'mutation($input: ApplyCouponInput!) { applyCoupon(input: $input) '
            '{ errors { code message } } }'
        )
        resp = self.client.post(
            '/graphql/',
            data={'query': query, 'variables': {'input': {'cartId': str(c.pk), 'code': code}}},
            content_type='application/json',
        )
        c.refresh_from_db()
        return c, resp.json()['data']['applyCoupon']['errors']

    def test_a_code_for_the_cart_is_applied(self):
        coupon = _coupon()
        coupon.applicable_products.add(self.mug)
        c, errors = self._apply('SAVE10', (self.mug, 60, 1))
        self.assertEqual(errors, [])
        self.assertEqual(c.coupon_id, coupon.pk)

    def test_a_code_for_other_products_is_refused(self):
        coupon = _coupon()
        coupon.applicable_products.add(self.novel)
        c, errors = self._apply('SAVE10', (self.mug, 60, 1))
        self.assertEqual(
            errors,
            [
                {
                    'code': 'INVALID_COUPON',
                    'message': "This code doesn't apply to anything in your cart.",
                }
            ],
        )
        self.assertIsNone(c.coupon_id)

    def test_an_expired_code_is_refused(self):
        from django.utils import timezone

        _coupon(expires_at=timezone.now() - timezone.timedelta(days=1))
        c, errors = self._apply('SAVE10', (self.mug, 60, 1))
        self.assertEqual(errors[0]['message'], 'This code has expired or is no longer active.')
        self.assertIsNone(c.coupon_id)


class FreeShippingUsageTests(TestCase):
    def test_a_free_shipping_code_counts_as_used(self):
        coupon = _coupon('SHIPFREE', 'free_shipping', 0, usage_limit=1)
        shopper = get_user_model().objects.create_user(
            username='s@example.com', email='s@example.com', password='x'
        )
        c = cart((product('book', 20), 20, 1), customer=shopper, coupon=coupon)
        self.assertTrue(breakdown(c)['meta'].get('free_shipping'))
        OrderService.create_from_cart(c, shopper.email, ADDRESS, ADDRESS)
        coupon.refresh_from_db()
        self.assertEqual(coupon.times_used, 1)
        self.assertFalse(coupon.is_valid)
