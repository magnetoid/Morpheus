"""Cart-mutation ownership (IDOR fix, v0.56.0).

Every cart mutation used to look a cart/item up by caller-supplied id and mutate
it with no ownership check, so any anonymous caller could empty, re-price, strip
the gift card off, or check out ANY cart whose id they could name. These lock
the fix: a non-owning session is refused (and the cart is left untouched), while
the owning session and a read:carts token still work.
"""

# ruff: noqa: PLC0415
from __future__ import annotations

from decimal import Decimal

from django.contrib.auth.models import AnonymousUser
from django.contrib.sessions.backends.db import SessionStore
from django.test import RequestFactory, TestCase
from djmoney.money import Money

from plugins.installed.catalog.models import Product
from plugins.installed.orders.graphql.mutations import (
    AddToCartInput,
    ApplyCouponInput,
    OrdersMutationExtension,
    SetShippingRateInput,
    UpdateCartItemInput,
)
from plugins.installed.orders.services import CartService


class _Info:
    def __init__(self, request):
        self.context = {'request': request}


def _session():
    s = SessionStore()
    s.create()
    return s


def _req(session, *, user=None, graphql_scopes=None):
    req = RequestFactory().post('/graphql/')
    req.session = session
    req.user = user or AnonymousUser()
    if graphql_scopes is not None:
        req._morph_token_scopes_graphql = set(graphql_scopes)
    return req


class CartMutationOwnershipTests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(
            name='Owned Book',
            slug='owned-book',
            sku='OWN-1',
            price=Money(Decimal('12.00'), 'USD'),
            status='active',
        )
        self.owner_session = _session()
        self.cart = CartService.get_or_create_cart(session_key=self.owner_session.session_key)
        self.item = CartService.add_item(self.cart, str(self.product.id), quantity=2)
        self.attacker_session = _session()
        self.mut = OrdersMutationExtension()

    # ── attacker is refused, cart unchanged ──────────────────────────────────
    def test_foreign_session_cannot_update_item(self):
        info = _Info(_req(self.attacker_session))
        payload = self.mut.update_cart_item(
            info, UpdateCartItemInput(item_id=str(self.item.id), quantity=99)
        )
        self.assertIsNone(payload.cart)
        self.assertEqual(payload.errors[0].code, 'NOT_FOUND')
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity, 2, 'attacker must not have changed the quantity')

    def test_foreign_session_cannot_set_shipping_rate(self):
        info = _Info(_req(self.attacker_session))
        payload = self.mut.set_shipping_rate(
            info, SetShippingRateInput(cart_id=str(self.cart.id), shipping_rate_id='evil')
        )
        self.assertEqual(payload.errors[0].code, 'NOT_FOUND')
        self.cart.refresh_from_db()
        self.assertNotIn('shipping_rate_id', self.cart.metadata or {})

    def test_foreign_session_cannot_apply_coupon(self):
        info = _Info(_req(self.attacker_session))
        payload = self.mut.apply_coupon(info, ApplyCouponInput(cart_id=str(self.cart.id), code='X'))
        self.assertEqual(payload.errors[0].code, 'NOT_FOUND')

    def test_foreign_session_cannot_complete_order(self):
        info = _Info(_req(self.attacker_session))
        from plugins.installed.orders.graphql.inputs import AddressInput
        from plugins.installed.orders.graphql.mutations import CompleteOrderInput
        from plugins.installed.orders.models import Order

        payload = self.mut.complete_order(
            info,
            CompleteOrderInput(
                cart_id=str(self.cart.id),
                email='attacker@evil.test',
                shipping_address=AddressInput(country='US'),
            ),
        )
        self.assertEqual(payload.errors[0].code, 'NOT_FOUND')
        self.assertEqual(
            Order.objects.count(), 0, 'no order may be minted from another session cart'
        )

    # ── owner still works ────────────────────────────────────────────────────
    def test_owner_can_update_item(self):
        info = _Info(_req(self.owner_session))
        payload = self.mut.update_cart_item(
            info, UpdateCartItemInput(item_id=str(self.item.id), quantity=5)
        )
        self.assertEqual(payload.errors, [])
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity, 5)

    # ── read:carts token is the escape hatch ─────────────────────────────────
    def test_read_carts_token_can_mutate(self):
        info = _Info(_req(self.attacker_session, graphql_scopes={'read:carts'}))
        payload = self.mut.set_shipping_rate(
            info, SetShippingRateInput(cart_id=str(self.cart.id), shipping_rate_id='r1')
        )
        self.assertEqual(payload.errors, [])

    # ── addToCart ignores a caller-supplied session_key ──────────────────────
    def test_add_to_cart_ignores_supplied_session_key(self):
        # Owner adds, but tries to pass the ATTACKER's key — the item must land
        # in the owner's own (request-session) cart, never the attacker's.
        info = _Info(_req(self.owner_session))
        payload = self.mut.add_to_cart(
            info,
            AddToCartInput(
                product_id=str(self.product.id),
                quantity=1,
                session_key=self.attacker_session.session_key,
            ),
        )
        self.assertEqual(payload.errors, [])
        self.assertEqual(payload.cart.session_key, self.owner_session.session_key)
        from plugins.installed.orders.models import Cart

        foreign_exists = Cart.objects.filter(session_key=self.attacker_session.session_key).exists()
        self.assertFalse(foreign_exists, 'no cart should exist for the supplied foreign key')

    # ── CartType.sessionKey no longer leaks (through the real schema) ─────────
    def test_cart_type_session_key_is_blanked(self):
        from api.client import internal_graphql

        data = internal_graphql(
            'query C($id: ID!){ cart(id:$id){ id sessionKey } }',
            {'id': str(self.cart.id)},
            request=_req(self.owner_session),
        )
        self.assertIsNotNone(data['cart'])
        self.assertEqual(data['cart']['sessionKey'], '')
