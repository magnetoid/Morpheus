"""Linda's promotion and coupon tools write through the same rules as the
dashboard, and every write waits for the merchant's yes."""

from __future__ import annotations

from decimal import Decimal

from django.test import TestCase

from morpheus.core import ToolError, agent_registry
from plugins.installed.marketing.models import Coupon
from plugins.installed.promotions.models import Promotion

from ._fixtures import category, product, promotion

WRITES = ['promotions.create', 'promotions.update', 'coupons.create', 'coupons.update']


def _call(tool_name, **args):
    return agent_registry.get_tool(tool_name).invoke(args)


class ToolContractTests(TestCase):
    def test_every_write_needs_approval_and_a_write_scope(self):
        for name in WRITES:
            tool = agent_registry.get_tool(name)
            self.assertTrue(tool.requires_approval, name)
            self.assertEqual(list(tool.scopes), ['promotions.write'], name)

    def test_the_reads_need_the_read_scope(self):
        for name in ('promotions.list', 'coupons.list'):
            self.assertEqual(list(agent_registry.get_tool(name).scopes), ['promotions.read'])


class PromotionToolTests(TestCase):
    def test_create_a_gift_promotion(self):
        bookmark = product('bookmark', 3)
        result = _call(
            'promotions.create',
            name='Free bookmark',
            kind='gift',
            gift_product='BOOKMARK',
            min_subtotal=30,
        )
        promo = Promotion.objects.get(slug='free-bookmark')
        self.assertEqual(result.output['id'], str(promo.pk))
        self.assertTrue(promo.is_active and promo.combinable)
        rule = promo.rules.get()
        self.assertEqual(rule.action, {'kind': 'gift', 'product_id': str(bookmark.pk)})
        self.assertEqual(rule.predicates, {'min_subtotal': 30.0})

    def test_create_refuses_a_bad_value(self):
        with self.assertRaises(ToolError):
            _call('promotions.create', name='Too much', kind='percent_off', value=150)
        self.assertFalse(Promotion.objects.exists())

    def test_update_changes_only_what_it_is_given(self):
        category('fiction')
        promo = promotion(
            'Ten', {'kind': 'percent_off', 'value': 10}, {'category_slugs': ['fiction']}, priority=7
        )
        _call('promotions.update', promotion='ten', is_active=False)
        promo.refresh_from_db()
        self.assertFalse(promo.is_active)
        self.assertEqual(promo.priority, 7)
        rule = promo.rules.get()
        self.assertEqual(rule.action, {'kind': 'percent_off', 'value': 10.0})
        self.assertEqual(rule.predicates, {'category_slugs': ['fiction']})

    def test_update_keeps_a_buy_x_get_y_rules_products(self):
        book = product('book', 20)
        promo = promotion(
            'Two plus one',
            {'kind': 'bogo', 'buy_qty': 2, 'free_qty': 1, 'product_ids': [str(book.pk)]},
        )
        _call('promotions.update', promotion='two-plus-one', name='Renamed')
        rule = promo.rules.get()
        self.assertEqual(rule.action['product_ids'], [str(book.pk)])

    def test_update_an_unknown_promotion(self):
        with self.assertRaises(ToolError):
            _call('promotions.update', promotion='nope', is_active=False)


class CouponToolTests(TestCase):
    def test_create_a_scoped_coupon(self):
        fiction = category('fiction')
        result = _call(
            'coupons.create',
            code='fiction10',
            discount_type='percentage',
            discount_value=10,
            categories=['fiction'],
            exclude_sale_items=True,
        )
        coupon = Coupon.objects.get(code='FICTION10')
        self.assertEqual(result.output['categories'], ['fiction'])
        self.assertEqual(list(coupon.applicable_categories.all()), [fiction])
        self.assertTrue(coupon.exclude_sale_items)
        self.assertEqual(coupon.discount_value, Decimal('10'))

    def test_create_refuses_a_taken_code_and_an_unknown_product(self):
        _call('coupons.create', code='TEN', discount_type='percentage', discount_value=10)
        with self.assertRaises(ToolError):
            _call('coupons.create', code='ten', discount_type='percentage', discount_value=5)
        with self.assertRaises(ToolError):
            _call(
                'coupons.create',
                code='X',
                discount_type='percentage',
                discount_value=5,
                products=['NOPE'],
            )
        self.assertEqual(Coupon.objects.count(), 1)

    def test_update_switches_a_coupon_off(self):
        _call('coupons.create', code='TEN', discount_type='percentage', discount_value=10)
        _call('coupons.update', code='ten', is_active=False)
        coupon = Coupon.objects.get(code='TEN')
        self.assertFalse(coupon.is_active)
        self.assertEqual(coupon.discount_value, Decimal('10'))

    def test_buy_x_get_y(self):
        _call(
            'coupons.create',
            code='B2G1',
            discount_type='buy_x_get_y',
            discount_value=100,
            buy_quantity=2,
            get_quantity=1,
        )
        coupon = Coupon.objects.get()
        self.assertEqual((coupon.buy_quantity, coupon.get_quantity), (2, 1))
