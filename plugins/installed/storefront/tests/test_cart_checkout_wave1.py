"""Wave 1 cart/checkout conversion wins (docs/plans/cutting-edge-open-core-2026-07.md):
line-quantity editing, promo-code apply/remove on the live one-page path,
and BEGIN_CHECKOUT firing there (cart_abandonment/analytics were blind)."""

from __future__ import annotations

from django.test import Client, TestCase
from djmoney.money import Money

from core.hooks import MorpheusEvents, hook_registry
from plugins.installed.catalog.models import Product
from plugins.installed.customers.models import Customer
from plugins.installed.orders.models import Cart, CartItem


class _Base(TestCase):
    def setUp(self) -> None:
        self.c = Client()
        self.customer = Customer.objects.create_user(
            email='buyer@example.test', username='buyer', password='x'
        )
        self.c.force_login(self.customer)
        self.product = Product.objects.create(
            name='Wave One Book',
            slug='wave-one-book',
            sku='W1B',
            price=Money(20, 'USD'),
            status='active',
        )
        self.cart = Cart.objects.create(customer=self.customer)
        self.item = CartItem.objects.create(
            cart=self.cart, product=self.product, quantity=2, unit_price=Money(20, 'USD')
        )


class CartUpdateTests(_Base):
    def _post(self, quantity, item=None):
        return self.c.post(f'/cart/update/{(item or self.item).id}/', {'quantity': str(quantity)})

    def test_increase_quantity(self):
        resp = self._post(3)
        self.assertEqual(resp.status_code, 302)
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity, 3)

    def test_zero_removes_the_line(self):
        self._post(0)
        self.assertFalse(CartItem.objects.filter(pk=self.item.pk).exists())

    def test_clamped_to_99(self):
        self._post(500)
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity, 99)

    def test_cannot_touch_another_shoppers_line(self):
        other = Customer.objects.create_user(email='o@example.test', username='o', password='x')
        other_cart = Cart.objects.create(customer=other)
        other_item = CartItem.objects.create(
            cart=other_cart, product=self.product, quantity=1, unit_price=Money(20, 'USD')
        )
        resp = self._post(5, item=other_item)
        self.assertEqual(resp.status_code, 404)
        other_item.refresh_from_db()
        self.assertEqual(other_item.quantity, 1)

    def test_get_not_allowed(self):
        resp = self.c.get(f'/cart/update/{self.item.id}/')
        self.assertEqual(resp.status_code, 405)


class CouponOnLivePathTests(_Base):
    def setUp(self) -> None:
        super().setUp()
        from plugins.installed.marketing.models import Coupon

        self.coupon = Coupon.objects.create(
            code='TEN-OFF', discount_type='percentage', discount_value=10, is_active=True
        )
        session = self.c.session
        session['cart_id'] = str(self.cart.id)
        session.save()

    def test_apply_valid_code(self):
        resp = self.c.post('/checkout/coupon/apply/', {'code': 'TEN-OFF'})
        self.assertEqual(resp.status_code, 302)
        self.assertNotIn('coupon=invalid', resp['Location'])
        self.cart.refresh_from_db()
        self.assertEqual(self.cart.coupon_id, self.coupon.id)

    def test_invalid_code_redirects_with_flag(self):
        resp = self.c.post('/checkout/coupon/apply/', {'code': 'NOPE'})
        self.assertIn('coupon=invalid', resp['Location'])
        self.cart.refresh_from_db()
        self.assertIsNone(self.cart.coupon_id)

    def test_remove_clears_the_coupon(self):
        self.cart.coupon = self.coupon
        self.cart.save(update_fields=['coupon'])
        resp = self.c.post('/checkout/coupon/remove/')
        self.assertEqual(resp.status_code, 302)
        self.cart.refresh_from_db()
        self.assertIsNone(self.cart.coupon_id)


class CheckoutEmailStampTests(_Base):
    def test_one_page_submit_stamps_email_on_cart(self):
        # Validation will fail (no address) — the stamp must land anyway, so
        # an abandoned attempt is still recoverable.
        self.c.post('/checkout/quick/', {'email': 'buyer@example.test'})
        self.cart.refresh_from_db()
        self.assertEqual(self.cart.metadata.get('checkout_email'), 'buyer@example.test')

    def test_garbage_email_not_stamped(self):
        self.c.post('/checkout/quick/', {'email': 'not-an-email'})
        self.cart.refresh_from_db()
        self.assertNotIn('checkout_email', self.cart.metadata or {})


class BeginCheckoutOnLivePathTests(_Base):
    def test_fires_once_per_session_on_quick_checkout(self):
        fired: list = []
        hook_registry.register(
            MorpheusEvents.BEGIN_CHECKOUT, lambda **kw: fired.append(kw), plugin=None
        )
        try:
            self.c.get('/checkout/quick/')
            self.c.get('/checkout/quick/')
        finally:
            # test-local subscriber; the registry has no unregister-by-handler,
            # so drop the whole event key (nothing else subscribes in tests).
            hook_registry._handlers.get(MorpheusEvents.BEGIN_CHECKOUT, []).clear()
        self.assertEqual(len(fired), 1)
        self.assertEqual(fired[0]['cart'].id, self.cart.id)
        self.assertEqual(fired[0]['customer'], self.customer)
