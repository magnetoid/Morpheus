"""Contract tests for checkout payment-gateway routing.

This is the live money path. These tests exercise the REAL
``gateway_registry`` + the REAL ``PaymentGateway`` ABC implementations
(stripe / manual / cod / test) — only the external Stripe SDK boundary
(``stripe.PaymentIntent.create``) is mocked. The point is to prove:

* the Stripe path still returns the Stripe intent shape (``client_secret``
  + ``transaction_id``) via the unchanged ``PaymentService`` — selecting
  'stripe' is byte-for-byte the pre-routing call;
* manual / cod / test return their offline success dicts;
* an empty / unknown / disabled slug falls back to the default — Stripe when
  it is set up, else the first method that can take payment — never the
  disabled gateway;
* a gateway that is not set up (Stripe without keys, bank transfer without
  bank details) is never offered, and nothing set up is a clear error;
* the sandbox gateway is offered to staff only;
* the resolved slug is recorded on ``order.payment_gateway`` for refund
  routing.
"""

from __future__ import annotations

from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.contrib.sessions.backends.db import SessionStore
from django.test import RequestFactory, TestCase, override_settings
from djmoney.money import Money

from plugins.installed.catalog.models import Product
from plugins.installed.orders.graphql.inputs import AddressInput
from plugins.installed.orders.graphql.mutations import (
    CompleteOrderInput,
    OrdersMutationExtension,
)
from plugins.installed.orders.models import Cart, CartItem, Order
from plugins.installed.payments.gateway import PaymentGateway, gateway_registry
from plugins.installed.payments.models import PaymentGatewayConfig, PaymentTransaction
from plugins.installed.payments.services import routing

# Stripe counts as set up only with both keys; bank transfer only with bank details.
# Fake key strings, never real keys; kept in names so no key literal is committed.
FAKE_SECRET, FAKE_PUBLIC, FAKE_LIVE_SECRET = 'sk_test_x', 'pk_test_x', 'sk_live_x'
STRIPE_READY = override_settings(STRIPE_SECRET_KEY=FAKE_SECRET, STRIPE_PUBLIC_KEY=FAKE_PUBLIC)
NO_STRIPE = override_settings(STRIPE_SECRET_KEY='', STRIPE_PUBLIC_KEY='')
BANK_DETAILS = {'instructions': 'Wire to IBAN 123.'}


def _make_order(amount='42', customer=None):
    """A real, saved Order (routing records the slug on it)."""
    return Order.objects.create(
        email='shopper@example.com',
        customer=customer,
        subtotal=Money(Decimal(amount), 'USD'),
        total=Money(Decimal(amount), 'USD'),
    )


def _staff():
    return get_user_model().objects.create_user(
        username='routing-staff', email='staff@example.com', password='x', is_staff=True
    )


def _bank_transfer_set_up():
    PaymentGatewayConfig.objects.update_or_create(
        slug='manual', defaults={'enabled': True, 'config': BANK_DETAILS}
    )


def _gateway_of(order):
    """Read the persisted payment_gateway without refresh_from_db().

    ``Order.status`` is a protected FSMField; ``refresh_from_db`` tries to
    re-assign it and django-fsm raises. A targeted query sidesteps that.
    """
    return Order.objects.values_list('payment_gateway', flat=True).get(pk=order.pk)


class _FakeIntent:
    """Mirrors the attributes routing/PaymentService read off a Stripe PI."""

    id = 'pi_test_123'
    client_secret = 'pi_test_123_secret_abc'


@STRIPE_READY
class ResolveGatewayTests(TestCase):
    """resolve_gateway() — pure validation against the real registry."""

    def setUp(self):
        _bank_transfer_set_up()

    def test_registry_has_expected_gateways(self):
        # Sanity: the real gateways are registered (payments +
        # advanced_payments ready() ran at app load).
        self.assertIsNotNone(gateway_registry.get('stripe'))
        self.assertIsNotNone(gateway_registry.get('manual'))
        self.assertIsNotNone(gateway_registry.get('cod'))
        self.assertIsNotNone(gateway_registry.get('test'))

    def test_default_is_stripe(self):
        self.assertEqual(gateway_registry.default().slug, 'stripe')

    def test_empty_slug_resolves_to_default(self):
        self.assertEqual(routing.resolve_gateway('').slug, 'stripe')
        self.assertEqual(routing.resolve_gateway(None).slug, 'stripe')

    def test_unknown_slug_falls_back_to_default(self):
        self.assertEqual(routing.resolve_gateway('bogus_pay').slug, 'stripe')

    def test_enabled_slug_resolves_to_that_gateway(self):
        # manual ships enabled by default; setUp gave it bank details.
        self.assertEqual(routing.resolve_gateway('manual').slug, 'manual')

    def test_disabled_slug_falls_back_to_default(self):
        # 'test' is OFF by default (not in DEFAULT_ENABLED) → rejected,
        # falls back to stripe rather than honouring the client's pick.
        self.assertEqual(routing.resolve_gateway('test').slug, 'stripe')

    def test_explicitly_disabled_slug_is_rejected(self):
        PaymentGatewayConfig.objects.filter(slug='manual').update(enabled=False)
        self.assertEqual(routing.resolve_gateway('manual').slug, 'stripe')

    def test_resolved_gateway_is_a_real_abc_instance(self):
        self.assertIsInstance(routing.resolve_gateway('manual'), PaymentGateway)


@STRIPE_READY
class CreatePaymentIntentRoutingTests(TestCase):
    """create_payment_intent_for() — the routed money path per gateway."""

    def setUp(self):
        _bank_transfer_set_up()

    def test_stripe_path_returns_stripe_intent_shape(self):
        order = _make_order('19')
        # Mock ONLY the external Stripe SDK boundary; the StripeGateway +
        # PaymentService + registry are all real. This proves selecting
        # 'stripe' produces the same intent shape as the pre-routing call.
        with (
            mock.patch(
                'plugins.installed.payments.services.stripe.PaymentService.get_stripe_api_key',
                return_value='sk_test_x',
            ),
            mock.patch(
                'plugins.installed.payments.services.stripe.stripe.PaymentIntent.create',
                return_value=_FakeIntent(),
            ),
        ):
            result = routing.create_payment_intent_for(order, 'stripe')

        self.assertTrue(result['success'])
        self.assertEqual(result['client_secret'], 'pi_test_123_secret_abc')
        # A real PaymentTransaction row was written by PaymentService.
        self.assertIn('transaction_id', result)
        tx = PaymentTransaction.objects.get(id=result['transaction_id'])
        self.assertEqual(tx.provider, 'stripe')
        self.assertEqual(tx.provider_transaction_id, 'pi_test_123')
        # Routing recorded the slug for refunds.
        self.assertEqual(_gateway_of(order), 'stripe')

    def test_empty_slug_uses_stripe_default(self):
        order = _make_order()
        with (
            mock.patch(
                'plugins.installed.payments.services.stripe.PaymentService.get_stripe_api_key',
                return_value='sk_test_x',
            ),
            mock.patch(
                'plugins.installed.payments.services.stripe.stripe.PaymentIntent.create',
                return_value=_FakeIntent(),
            ),
        ):
            result = routing.create_payment_intent_for(order, '')
        self.assertTrue(result['success'])
        self.assertEqual(result['client_secret'], 'pi_test_123_secret_abc')
        self.assertEqual(_gateway_of(order), 'stripe')

    def test_manual_returns_offline_success(self):
        order = _make_order()
        result = routing.create_payment_intent_for(order, 'manual')
        self.assertTrue(result['success'])
        # Offline gateways don't issue a client_secret.
        self.assertFalse(result.get('client_secret'))
        self.assertEqual(_gateway_of(order), 'manual')

    def test_cod_returns_offline_success_when_enabled(self):
        PaymentGatewayConfig.objects.update_or_create(slug='cod', defaults={'enabled': True})
        order = _make_order()
        result = routing.create_payment_intent_for(order, 'cod')
        self.assertTrue(result['success'])
        self.assertIn('cod_', result['transaction_id'])
        self.assertEqual(_gateway_of(order), 'cod')

    def test_test_gateway_returns_success_when_enabled(self):
        PaymentGatewayConfig.objects.update_or_create(slug='test', defaults={'enabled': True})
        order = _make_order(customer=_staff())  # the sandbox is offered to staff only
        result = routing.create_payment_intent_for(order, 'test')
        self.assertTrue(result['success'])
        self.assertIn('test_', result['transaction_id'])
        self.assertEqual(_gateway_of(order), 'test')

    def test_disabled_slug_falls_back_to_stripe_default(self):
        # 'test' is disabled by default → must route to stripe, NOT test.
        order = _make_order()
        with (
            mock.patch(
                'plugins.installed.payments.services.stripe.PaymentService.get_stripe_api_key',
                return_value='sk_test_x',
            ),
            mock.patch(
                'plugins.installed.payments.services.stripe.stripe.PaymentIntent.create',
                return_value=_FakeIntent(),
            ),
        ):
            result = routing.create_payment_intent_for(order, 'test')
        self.assertTrue(result['success'])
        self.assertEqual(result['client_secret'], 'pi_test_123_secret_abc')
        self.assertEqual(_gateway_of(order), 'stripe')

    def test_unknown_slug_falls_back_to_stripe_default(self):
        order = _make_order()
        with (
            mock.patch(
                'plugins.installed.payments.services.stripe.PaymentService.get_stripe_api_key',
                return_value='sk_test_x',
            ),
            mock.patch(
                'plugins.installed.payments.services.stripe.stripe.PaymentIntent.create',
                return_value=_FakeIntent(),
            ),
        ):
            result = routing.create_payment_intent_for(order, 'totally-made-up')
        self.assertTrue(result['success'])
        self.assertEqual(_gateway_of(order), 'stripe')

    def test_gateway_exception_fails_soft_not_500(self):
        # A gateway that raises must surface a {success: False} dict, never
        # propagate — checkout must not 500.
        order = _make_order()
        boom = mock.Mock(side_effect=RuntimeError('provider down'))
        with mock.patch.object(routing, 'resolve_gateway') as rg:
            rg.return_value = mock.Mock(slug='stripe', create_payment_intent=boom)
            result = routing.create_payment_intent_for(order, 'stripe')
        self.assertFalse(result['success'])
        self.assertIn('provider down', result['error'])


@STRIPE_READY
class PickerGatewaysTests(TestCase):
    """picker_gateways() — checkout UI list honours enable flags + default."""

    def setUp(self):
        _bank_transfer_set_up()

    def test_lists_enabled_only_with_default_flag(self):
        methods = routing.picker_gateways()
        slugs = {m['slug'] for m in methods}
        # stripe + manual ship enabled (and are set up here); test is off by default.
        self.assertIn('stripe', slugs)
        self.assertIn('manual', slugs)
        self.assertNotIn('test', slugs)
        # Exactly one default, and it's stripe.
        defaults = [m['slug'] for m in methods if m['is_default']]
        self.assertEqual(defaults, ['stripe'])
        # Each entry carries a label + capability hint.
        for m in methods:
            self.assertTrue(m['label'])
            self.assertTrue(m['capability'])

    def test_disabled_gateway_drops_out_of_picker(self):
        PaymentGatewayConfig.objects.filter(slug='manual').update(enabled=False)
        slugs = {m['slug'] for m in routing.picker_gateways()}
        self.assertNotIn('manual', slugs)
        self.assertIn('stripe', slugs)

    def test_configured_instructions_surface(self):
        manual = next(m for m in routing.picker_gateways() if m['slug'] == 'manual')
        self.assertEqual(manual['instructions'], 'Wire to IBAN 123.')


@NO_STRIPE
class UnconfiguredGatewayTests(TestCase):
    """What the live stores had: no Stripe keys and no bank details, so the
    checkout pre-selected Stripe and the shopper got Stripe's raw error."""

    def setUp(self):
        PaymentGatewayConfig.objects.update_or_create(slug='cod', defaults={'enabled': True})

    def test_stripe_without_keys_is_not_offered_or_the_default(self):
        slugs = [m['slug'] for m in routing.picker_gateways()]
        self.assertNotIn('stripe', slugs)
        self.assertEqual(gateway_registry.default().slug, 'cod')

    def test_stripe_needs_both_keys(self):
        with override_settings(STRIPE_SECRET_KEY=FAKE_SECRET):
            self.assertNotIn('stripe', [m['slug'] for m in routing.picker_gateways()])

    def test_bank_transfer_is_offered_only_with_bank_details(self):
        self.assertNotIn('manual', [m['slug'] for m in routing.picker_gateways()])
        _bank_transfer_set_up()
        self.assertIn('manual', [m['slug'] for m in routing.picker_gateways()])

    def test_the_picker_pre_selects_a_method_that_works(self):
        defaults = [m['slug'] for m in routing.picker_gateways() if m['is_default']]
        self.assertEqual(defaults, ['cod'])

    def test_an_empty_choice_places_the_order_by_the_working_method(self):
        order = _make_order()
        result = routing.create_payment_intent_for(order, '')
        self.assertTrue(result['success'])
        self.assertEqual(_gateway_of(order), 'cod')

    def test_nothing_set_up_is_a_clear_error(self):
        PaymentGatewayConfig.objects.filter(slug='cod').update(enabled=False)
        result = routing.create_payment_intent_for(_make_order(), '')
        self.assertFalse(result['success'])
        self.assertIn("can't take payments", result['error'])

    def test_stripe_without_a_key_says_so_plainly(self):
        from plugins.installed.payments.services.stripe import PaymentService

        result = PaymentService.create_payment_intent(_make_order())
        self.assertFalse(result['success'])
        self.assertEqual(result['error'], 'Card payments are not set up for this store yet.')

    def test_stripe_error_text_never_reaches_the_shopper(self):
        import stripe

        from plugins.installed.payments.services.stripe import PaymentService

        leak = stripe.error.AuthenticationError('Invalid API Key provided: sk_live_****1234')
        with (
            override_settings(STRIPE_SECRET_KEY=FAKE_LIVE_SECRET),
            mock.patch(
                'plugins.installed.payments.services.stripe.stripe.PaymentIntent.create',
                side_effect=leak,
            ),
        ):
            result = PaymentService.create_payment_intent(_make_order())
        self.assertFalse(result['success'])
        self.assertNotIn('sk_live', result['error'])

    def test_the_sandbox_is_offered_to_staff_only(self):
        PaymentGatewayConfig.objects.update_or_create(slug='test', defaults={'enabled': True})
        staff = _staff()
        self.assertNotIn('test', [m['slug'] for m in routing.picker_gateways()])
        self.assertIn('test', [m['slug'] for m in routing.picker_gateways(user=staff)])
        # A shopper naming it is routed to a real method; staff get the sandbox.
        self.assertEqual(routing.resolve_gateway('test').slug, 'cod')
        order = _make_order(customer=staff)
        self.assertTrue(routing.create_payment_intent_for(order, 'test')['success'])
        self.assertEqual(_gateway_of(order), 'test')
        # Staff testing still get a real method pre-selected, not the sandbox.
        self.assertEqual(gateway_registry.default(user=staff).slug, 'cod')


class CompleteOrderWiringTests(TestCase):
    """Proves the completeOrder resolver threads the chosen slug into the
    router. ``OrderService.create_from_cart`` is stubbed (returns a real
    saved Order) so this exercises the resolver→routing wiring without the
    cart/product hook cascade — the routing behaviour itself is covered by
    the suites above.

    The cart is REAL and owned by the caller's session. Since the v0.56.0 IDOR
    fix the resolver runs ``load_owned_cart`` before anything else, so a mocked
    ``Cart`` class — which has no owner — is refused with NOT_FOUND and the
    router is never reached.
    """

    def setUp(self):
        self.session = SessionStore()
        self.session.create()
        product = Product.objects.create(
            name='Routed Book',
            slug='routed-book',
            sku='ROUTE-1',
            price=Money(Decimal('42.00'), 'USD'),
            status='active',
        )
        self.cart = Cart.objects.create(session_key=self.session.session_key)
        CartItem.objects.create(
            cart=self.cart,
            product=product,
            quantity=1,
            unit_price=Money(Decimal('42.00'), 'USD'),
        )

    def _info(self):
        request = RequestFactory().post('/graphql/')
        request.session = self.session
        request.user = AnonymousUser()
        info = mock.Mock()
        info.context = {'request': request}
        return info

    def test_resolver_passes_selected_slug_to_router(self):
        order = _make_order()
        ext = OrdersMutationExtension()
        inp = CompleteOrderInput(
            cart_id=str(self.cart.pk),
            email='x@y.com',
            shipping_address=AddressInput(country='US'),
            payment_gateway='manual',
        )
        with (
            mock.patch(
                'plugins.installed.orders.services.OrderService.create_from_cart',
                return_value=order,
            ),
            mock.patch(
                'plugins.installed.payments.services.routing.create_payment_intent_for'
            ) as router,
        ):
            router.return_value = {'success': True, 'client_secret': ''}
            res = ext.complete_order(self._info(), inp)

        self.assertFalse(res.errors, msg=str(res.errors))
        # The router was called with the order + the shopper's chosen slug.
        router.assert_called_once()
        called_order, called_slug = router.call_args.args
        self.assertEqual(called_order, order)
        self.assertEqual(called_slug, 'manual')
