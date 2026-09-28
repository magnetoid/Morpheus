from __future__ import annotations

import uuid
from decimal import Decimal

from django.test import TestCase
from django.test.utils import override_settings
from djmoney.money import Money

from morpheus.core import MorpheusEvents, hook_registry
from plugins.installed.catalog.models import Product, ProductVariant
from plugins.installed.customers.models import Customer
from plugins.installed.marketing.models import Coupon, CouponUsage
from plugins.installed.orders.services import CartService, OrderService
from plugins.installed.promotions.models import Promotion, PromotionApplication, PromotionRule


@override_settings(
    CACHES={
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'morpheus-test',
        }
    },
    CELERY_TASK_ALWAYS_EAGER=True,
    CELERY_TASK_EAGER_PROPAGATES=True,
    CELERY_BROKER_URL='memory://',
    CELERY_RESULT_BACKEND='cache+memory://',
)
class CheckoutTotalsBreakdownTests(TestCase):
    def setUp(self) -> None:
        self.product = Product.objects.create(
            name='Test Book', slug='test-book-2', sku='TB2', price=Money(20, 'USD'), status='active'
        )
        self.variant = ProductVariant.objects.create(
            product=self.product, name='Hardcover', sku='TB2-HC', price=Money(20, 'USD')
        )
        self.customer = Customer.objects.create_user(
            email='buyer2@example.com', username='buyer2', password='x'
        )

        self.coupon = Coupon.objects.create(
            code='SAVE5',
            name='Save $5',
            discount_type='fixed_amount',
            discount_value=Decimal('5.00'),
            is_active=True,
        )

        self.promo_id = uuid.uuid4()
        self.rule_id = uuid.uuid4()
        Promotion.objects.create(
            id=self.promo_id,
            name='Promo',
            slug='promo',
            type='order',
            is_active=True,
            priority=10,
        )
        PromotionRule.objects.create(
            id=self.rule_id,
            promotion_id=self.promo_id,
            label='Rule',
            predicates={},
            action={'kind': 'fixed_off', 'value': 5},
        )

        # Swap in a fake breakdown handler for this test only, and put the real
        # ones back after it. clear() alone wiped tax, shipping, promotions and
        # every other breakdown handler for each test that ran later in the same
        # process, so a state-tax test after it computed no tax at all.
        event = MorpheusEvents.CART_CALCULATE_BREAKDOWN
        saved = list(hook_registry._handlers.get(event, []))
        self.addCleanup(hook_registry._handlers.__setitem__, event, saved)
        hook_registry.clear(event)

        def handler(value, cart=None, address=None, shipping_rate_id=None, coupon=None, **kwargs):
            self.assertEqual(shipping_rate_id, 'rate_1')
            value['shipping'] = Money(Decimal('10.00'), 'USD')
            value['tax'] = Money(Decimal('4.00'), 'USD')
            value['discount'] = Money(Decimal('10.00'), 'USD')
            value['meta'] = {
                'shipping_rate_name': 'Flat',
                'coupon': {'code': 'SAVE5', 'discount_amount': '5.00'},
                'applied_promotions': [
                    {
                        'promotion_id': str(self.promo_id),
                        'promotion_name': 'Promo',
                        'rule_id': str(self.rule_id),
                        'discount_amount': '5.00',
                        'free_shipping': False,
                        'gift_product_id': None,
                        'note': 'Rule',
                    }
                ],
            }
            value['total'] = Money(Decimal('44.00'), 'USD')
            return value

        hook_registry.register(MorpheusEvents.CART_CALCULATE_BREAKDOWN, handler, priority=1)

    def test_breakdown_persists_totals_and_records_coupon_and_promotions(self):
        cart = CartService.get_or_create_cart(session_key='s-breakdown', customer=self.customer)
        CartService.add_item(
            cart, str(self.product.id), quantity=2, variant_id=str(self.variant.id)
        )
        cart.coupon = self.coupon
        cart.metadata = {'shipping_rate_id': 'rate_1'}
        cart.save(update_fields=['coupon', 'metadata', 'updated_at'])

        order = OrderService.create_from_cart(
            cart=cart,
            email='buyer2@example.com',
            shipping_address={'country': 'US', 'affiliate_code': 'AFF123'},
            billing_address={'country': 'US'},
        )

        self.assertEqual(order.subtotal.amount, Decimal('40.00'))
        self.assertEqual(order.shipping_total.amount, Decimal('10.00'))
        self.assertEqual(order.tax_total.amount, Decimal('4.00'))
        self.assertEqual(order.discount_total.amount, Decimal('10.00'))
        self.assertEqual(order.total.amount, Decimal('44.00'))
        self.assertEqual(order.shipping_method, 'Flat')
        self.assertEqual(order.coupon_code, 'SAVE5')
        self.assertEqual(order.source, 'affiliate:AFF123')

        self.coupon.refresh_from_db()
        self.assertEqual(self.coupon.times_used, 1)
        self.assertEqual(
            CouponUsage.objects.filter(
                coupon=self.coupon, customer=self.customer, order=order
            ).count(),
            1,
        )

        self.assertEqual(
            PromotionApplication.objects.filter(
                order_id=str(order.id), promotion_id=self.promo_id
            ).count(),
            1,
        )
