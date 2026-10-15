"""No conversion API sends what the shopper did not agree to.

Meta, TikTok, Pinterest, Snapchat and Reddit sent sha256(email) and the purchase
on ORDER_PAID whatever the shopper chose (wave 0 item 3). Each now asks
core.consent.allowed('marketing'): the order's stamp, else the request, else the
store — a store that manages consent refuses without evidence.
"""

from __future__ import annotations

import json
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.core.cache import cache
from django.test import RequestFactory, TestCase
from djmoney.money import Money

from plugins.registry import app_registry

PURCHASE = [
    ('meta_commerce', 'plugins.installed.meta_commerce.services.capi.send_purchase'),
    (
        'tiktok_commerce',
        'plugins.installed.tiktok_commerce.services.events_api.send_complete_payment',
    ),
    ('pinterest_commerce', 'plugins.installed.pinterest_commerce.services.capi.send_checkout'),
    ('snapchat_commerce', 'plugins.installed.snapchat_commerce.services.capi.send_purchase'),
    ('reddit_ads', 'plugins.installed.reddit_ads.services.capi.send_purchase'),
]
CART = [
    (
        'meta_commerce',
        '_on_add_to_cart',
        'plugins.installed.meta_commerce.services.capi.send_add_to_cart',
        'product',
    ),
    (
        'meta_commerce',
        '_on_begin_checkout',
        'plugins.installed.meta_commerce.services.capi.send_initiate_checkout',
        'cart',
    ),
    (
        'tiktok_commerce',
        '_on_add_to_cart',
        'plugins.installed.tiktok_commerce.services.events_api.send_add_to_cart',
        'product',
    ),
    (
        'tiktok_commerce',
        '_on_begin_checkout',
        'plugins.installed.tiktok_commerce.services.events_api.send_initiate_checkout',
        'cart',
    ),
    (
        'pinterest_commerce',
        '_on_add_to_cart',
        'plugins.installed.pinterest_commerce.services.capi.send_add_to_cart',
        'product',
    ),
]


def _set_gdpr(on: bool) -> None:
    from core.models import StoreSettings

    row = StoreSettings.objects.first() or StoreSettings()
    row.gdpr_enabled = on
    row.save()
    cache.delete('morph:gdpr_enabled')


def _order(consent=None):
    return SimpleNamespace(metadata={'consent': consent} if consent is not None else {})


def _request(marketing=None):
    req = RequestFactory().get('/')
    if marketing is not None:
        req.COOKIES['morpheus_consent'] = json.dumps({'necessary': True, 'marketing': marketing})
    return req


class PurchaseConsentTests(TestCase):
    def setUp(self):
        _set_gdpr(True)

    def _sent(self, app, path, order):
        with patch(path) as send:
            app_registry.get(app)._on_order_paid(order=order)
        return send.called

    def test_a_stamped_no_sends_nothing(self):
        for app, path in PURCHASE:
            with self.subTest(app=app):
                self.assertFalse(
                    self._sent(app, path, _order({'managed': True, 'marketing': False}))
                )

    def test_a_stamped_yes_sends(self):
        for app, path in PURCHASE:
            with self.subTest(app=app):
                self.assertTrue(self._sent(app, path, _order({'managed': True, 'marketing': True})))

    def test_an_unstamped_order_on_a_managed_store_sends_nothing(self):
        for app, path in PURCHASE:
            with self.subTest(app=app):
                self.assertFalse(self._sent(app, path, _order()))

    def test_a_store_that_does_not_manage_consent_sends_as_before(self):
        _set_gdpr(False)
        for app, path in PURCHASE:
            with self.subTest(app=app):
                self.assertTrue(self._sent(app, path, _order()))

    def test_a_real_paid_order_fired_through_the_bus_respects_its_stamp(self):
        # Review Focus 1: the payment webhook fires ORDER_PAID hours later with
        # the order alone; the stamp decides.
        from core.hooks import MorpheusEvents, hook_registry
        from plugins.installed.orders.models import Order

        order = Order.objects.create(
            email='late@x.test',
            subtotal=Money(Decimal('9'), 'USD'),
            total=Money(Decimal('9'), 'USD'),
            metadata={'consent': {'managed': True, 'analytics': True, 'marketing': False}},
        )
        with patch('plugins.installed.meta_commerce.services.capi.send_purchase') as send:
            hook_registry.fire(MorpheusEvents.ORDER_PAID, order=order)
        send.assert_not_called()


class CartEventConsentTests(TestCase):
    def setUp(self):
        _set_gdpr(True)

    def _sent(self, app, handler, path, arg, request):
        with patch(path) as send:
            getattr(app_registry.get(app), handler)(**{arg: object()}, request=request)
        return send.called

    def test_a_visitor_who_refused_is_not_sent(self):
        for app, handler, path, arg in CART:
            with self.subTest(app=app, handler=handler):
                self.assertFalse(self._sent(app, handler, path, arg, _request()))

    def test_a_visitor_who_accepted_is_sent(self):
        for app, handler, path, arg in CART:
            with self.subTest(app=app, handler=handler):
                self.assertTrue(self._sent(app, handler, path, arg, _request(marketing=True)))

    def test_an_unmanaged_store_sends_as_before(self):
        _set_gdpr(False)
        for app, handler, path, arg in CART:
            with self.subTest(app=app, handler=handler):
                self.assertTrue(self._sent(app, handler, path, arg, _request()))


class CartFiresCarryTheRequestTests(TestCase):
    def test_add_to_cart_passes_the_request(self):
        from core.hooks import MorpheusEvents, hook_registry
        from plugins.installed.catalog.models import Product

        product = Product.objects.create(
            name='Req', slug='req-carry', sku='REQ', price=Money(3, 'USD'), status='active'
        )
        seen = []

        def spy(**kw):
            seen.append(kw)

        hook_registry.register(MorpheusEvents.ADD_TO_CART, spy, plugin=None)
        self.addCleanup(hook_registry.unregister, MorpheusEvents.ADD_TO_CART, spy)
        self.client.post(f'/cart/add/{product.id}/', {'quantity': 1})
        self.assertTrue(seen)
        self.assertIsNotNone(seen[0].get('request'))
