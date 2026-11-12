"""Charging a card later (payments' ``capture_mode``, v0.155.0).

Until v0.155.0 every card payment was taken at checkout: the base gateway's
``capture()`` was the only one there was, and nothing could hold a payment
until the order shipped.
"""

# ruff: noqa: PLC0415
from __future__ import annotations

from types import SimpleNamespace
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from djmoney.money import Money

from morpheus.core import MorpheusEvents, hook_registry
from plugins.installed.payments.models import PaymentTransaction
from plugins.registry import app_registry

Status = PaymentTransaction.Status


def _fresh(order):
    # The order's status is a protected FSM field: refresh_from_db() raises.
    return type(order).objects.get(pk=order.pk)


def _intent(intent_id='pi_held', status='requires_payment_method'):
    return SimpleNamespace(id=intent_id, client_secret=f'{intent_id}_secret', status=status)


class CaptureTestBase(TestCase):
    def setUp(self):
        self.payments = app_registry.get('payments')
        self.addCleanup(self.payments.invalidate_config_cache)
        self.payments.set_config('stripe_secret_key', 'sk_test_x')
        from plugins.installed.catalog.models import Product

        self.mug = Product.objects.create(
            name='Mug', slug='mc-mug', sku='MC-MUG', price=Money(5, 'USD')
        )
        self.lamp = Product.objects.create(
            name='Lamp', slug='mc-lamp', sku='MC-LAMP', price=Money(20, 'USD')
        )
        self.ebook = Product.objects.create(
            name='Guide',
            slug='mc-guide',
            sku='MC-PDF',
            product_type='digital',
            requires_shipping=False,
            price=Money(8, 'USD'),
        )

    def _mode(self, mode):
        self.payments.set_config('capture_mode', mode)

    def _order(self, *lines, status='pending'):
        from plugins.installed.orders.models import Order, OrderItem

        order = Order.objects.create(
            email='buyer@example.com',
            subtotal=Money(25, 'USD'),
            total=Money(25, 'USD'),
            status=status,
            payment_gateway='stripe',
        )
        for product, qty in lines or ((self.mug, 1),):
            OrderItem.objects.create(
                order=order,
                product=product,
                product_name=product.name,
                sku=product.sku,
                quantity=qty,
                unit_price=product.price,
                total_price=product.price * qty,
            )
        return order

    def _start(self, order, intent_id='pi_held'):
        """Start the order's card payment; returns the PaymentIntent.create call."""
        from plugins.installed.payments.services.stripe import PaymentService

        with mock.patch('stripe.PaymentIntent.create', return_value=_intent(intent_id)) as create:
            result = PaymentService.create_payment_intent(order)
        self.assertTrue(result['success'])
        return create.call_args

    def _hold(self, order, intent_id='pi_held'):
        """Start the payment and let Stripe report the card authorized."""
        from plugins.installed.payments.services.stripe import PaymentService

        self._start(order, intent_id)
        PaymentService._mark_transaction_authorized(intent_id)
        return _fresh(order), PaymentTransaction.objects.get(provider_transaction_id=intent_id)

    def _listen(self, event):
        seen = []

        def handler(**kwargs):
            seen.append(kwargs)

        hook_registry.register(event, handler, plugin=None)
        self.addCleanup(hook_registry.unregister, event, handler)
        return seen

    def _ship(self, order, lines=None):
        from plugins.installed.orders.fulfilment import create_fulfillment

        with self.captureOnCommitCallbacks(execute=True):
            return create_fulfillment(order, lines)


class CaptureModeTests(CaptureTestBase):
    def test_by_default_the_card_is_charged_at_checkout_with_the_same_stripe_call(self):
        order = self._order()
        call = self._start(order)
        self.assertNotIn('capture_method', call.kwargs)
        self.assertEqual(call.kwargs['idempotency_key'], f'pi-{order.id}-2500')
        order = _fresh(order)
        self.assertEqual(order.metadata['capture_mode'], 'immediate')

    def test_a_parcel_mode_holds_the_card(self):
        self._mode('first_parcel')
        order = self._order()
        call = self._start(order)
        self.assertEqual(call.kwargs['capture_method'], 'manual')
        self.assertEqual(call.kwargs['idempotency_key'], f'pi-{order.id}-2500-manual')

    def test_the_mode_is_decided_once_per_order(self):
        self._mode('manual')
        order = self._order()
        self._start(order)
        self._mode('immediate')
        call = self._start(order)  # a retried payment keeps Stripe's parameters
        self.assertEqual(call.kwargs['capture_method'], 'manual')

    def test_an_order_with_a_download_is_charged_at_checkout_in_parcel_modes(self):
        for mode in ('first_parcel', 'all_shipped'):
            with self.subTest(mode=mode):
                self._mode(mode)
                order = self._order((self.mug, 1), (self.ebook, 1))
                self.assertNotIn('capture_method', self._start(order).kwargs)

    def test_manual_mode_holds_an_order_of_downloads_too(self):
        self._mode('manual')
        order = self._order((self.ebook, 1))
        self.assertEqual(self._start(order).kwargs['capture_method'], 'manual')

    def test_an_app_may_decide_per_order_and_nonsense_counts_as_immediate(self):
        answers = iter(['manual', 'whenever'])

        def decide(value, order=None, **kwargs):
            return next(answers)

        hook_registry.register(MorpheusEvents.PAYMENT_CAPTURE_MODE, decide, plugin=None)
        self.addCleanup(hook_registry.unregister, MorpheusEvents.PAYMENT_CAPTURE_MODE, decide)
        self.assertEqual(self._start(self._order()).kwargs['capture_method'], 'manual')
        self.assertNotIn('capture_method', self._start(self._order()).kwargs)


class AuthorizationTests(CaptureTestBase):
    def test_a_held_card_confirms_the_order_without_paying_it(self):
        self._mode('first_parcel')
        paid = self._listen(MorpheusEvents.ORDER_PAID)
        order = self._order()
        order, tx = self._hold(order)
        self.assertEqual(tx.status, Status.AUTHORIZED)
        self.assertIsNotNone(tx.authorized_at)
        self.assertEqual(order.payment_status, 'authorized')
        self.assertEqual(order.status, 'confirmed')
        self.assertEqual(paid, [])
        self.assertTrue(order.events.filter(event_type='PAYMENT_AUTHORIZED').exists())

    def test_the_webhook_records_the_hold_and_a_cancelled_intent(self):
        from plugins.installed.payments.services.stripe import PaymentService

        self._mode('manual')
        order = self._order()
        self._start(order)

        def deliver(event_id, event_type):
            event = SimpleNamespace(
                id=event_id,
                type=event_type,
                data=SimpleNamespace(object=SimpleNamespace(id='pi_held')),
                to_dict=lambda: {'id': event_id},
            )
            with mock.patch('stripe.Webhook.construct_event', return_value=event):
                PaymentService.process_webhook(b'{}', 'sig')

        deliver('evt_1', 'payment_intent.amount_capturable_updated')
        order = _fresh(order)
        self.assertEqual(order.payment_status, 'authorized')
        deliver('evt_2', 'payment_intent.canceled')
        order = _fresh(order)
        self.assertEqual(order.payment_status, 'released')
        self.assertEqual(
            PaymentTransaction.objects.get(provider_transaction_id='pi_held').status,
            Status.RELEASED,
        )

    def test_a_card_tried_after_a_declined_one_can_still_be_held(self):
        from plugins.installed.payments.services.stripe import PaymentService

        self._mode('manual')
        order = self._order()
        self._start(order)
        PaymentService._mark_transaction_failed('pi_held', 'Your card was declined.')
        PaymentService._mark_transaction_authorized('pi_held')
        order = _fresh(order)
        self.assertEqual(order.payment_status, 'authorized')

    def test_a_late_failure_never_undoes_a_hold(self):
        from plugins.installed.payments.services.stripe import PaymentService

        self._mode('manual')
        order = self._order()
        order, tx = self._hold(order)
        PaymentService._mark_transaction_failed('pi_held', 'late')
        tx.refresh_from_db()
        self.assertEqual(tx.status, Status.AUTHORIZED)


class CaptureTriggerTests(CaptureTestBase):
    def _captured(self):
        return mock.patch('stripe.PaymentIntent.capture', return_value=_intent(status='succeeded'))

    def test_the_first_parcel_charges_the_card_once(self):
        self._mode('first_parcel')
        paid = self._listen(MorpheusEvents.ORDER_PAID)
        order = self._order((self.mug, 2), (self.lamp, 1))
        order, tx = self._hold(order)
        mug = order.items.get(sku='MC-MUG')
        with self._captured() as capture:
            self._ship(order, {str(mug.pk): 1})
        capture.assert_called_once_with('pi_held', idempotency_key=f'capture-{tx.pk}')
        order = _fresh(order)
        tx.refresh_from_db()
        self.assertEqual((order.payment_status, tx.status), ('paid', Status.SUCCEEDED))
        self.assertEqual(len(paid), 1)
        with self._captured() as capture:
            self._ship(order)  # the second parcel finds nothing held
        capture.assert_not_called()

    def test_all_shipped_waits_for_the_last_parcel(self):
        self._mode('all_shipped')
        order = self._order((self.mug, 2), (self.lamp, 1))
        order, _ = self._hold(order)
        mug = order.items.get(sku='MC-MUG')
        with self._captured() as capture:
            self._ship(order, {str(mug.pk): 2})
        capture.assert_not_called()
        with self._captured() as capture:
            self._ship(order)
        capture.assert_called_once()

    def test_manual_mode_waits_for_the_merchant(self):
        self._mode('manual')
        order = self._order()
        order, _ = self._hold(order)
        with self._captured() as capture:
            self._ship(order)
        capture.assert_not_called()

    def test_an_order_fulfilled_without_a_parcel_is_charged(self):
        self._mode('all_shipped')
        order = self._order(status='processing')
        order, _ = self._hold(order)
        with self._captured() as capture, self.captureOnCommitCallbacks(execute=True):
            order.fulfill()
            order.save()
        capture.assert_called_once()

    def test_a_cancelled_order_gives_the_hold_back(self):
        self._mode('manual')
        order = self._order()
        order, tx = self._hold(order)
        with (
            mock.patch(
                'stripe.PaymentIntent.cancel', return_value=_intent(status='canceled')
            ) as cancel,
            self.captureOnCommitCallbacks(execute=True),
        ):
            order.cancel(reason='Customer asked')
            order.save()
        cancel.assert_called_once_with('pi_held')
        tx.refresh_from_db()
        order = _fresh(order)
        self.assertEqual((tx.status, order.payment_status), (Status.RELEASED, 'released'))

    def test_a_refused_charge_is_on_the_timeline_and_the_hold_stays(self):
        import stripe

        self._mode('manual')
        order = self._order()
        order, tx = self._hold(order)
        from plugins.installed.payments.services.capture import capture_order

        with (
            mock.patch(
                'stripe.PaymentIntent.capture',
                side_effect=stripe.error.InvalidRequestError('The hold expired', None),
            ),
            mock.patch(
                'stripe.PaymentIntent.retrieve', return_value=_intent(status='requires_capture')
            ),
        ):
            result = capture_order(order)
        self.assertFalse(result['success'])
        self.assertIn('The hold expired', result['error'])
        tx.refresh_from_db()
        self.assertEqual(tx.status, Status.AUTHORIZED)
        event = order.events.get(event_type='PAYMENT_CAPTURE_FAILED')
        self.assertIn('The hold expired', event.message)

    def test_a_payment_already_taken_in_stripe_counts_as_charged(self):
        import stripe

        self._mode('manual')
        order = self._order()
        order, _ = self._hold(order)
        from plugins.installed.payments.services.capture import capture_order

        with (
            mock.patch(
                'stripe.PaymentIntent.capture',
                side_effect=stripe.error.InvalidRequestError('already captured', None),
            ),
            mock.patch('stripe.PaymentIntent.retrieve', return_value=_intent(status='succeeded')),
        ):
            self.assertTrue(capture_order(order)['success'])
        order = _fresh(order)
        self.assertEqual(order.payment_status, 'paid')


class StaleHoldTests(CaptureTestBase):
    def _age(self, tx, days):
        PaymentTransaction.objects.filter(pk=tx.pk).update(
            authorized_at=timezone.now() - timezone.timedelta(days=days)
        )

    def test_a_hold_past_its_days_is_charged_by_default(self):
        from plugins.installed.payments.tasks import release_stale_authorizations

        self._mode('manual')
        old, fresh = self._order(), self._order()
        self._age(self._hold(old, 'pi_old')[1], 7)
        self._hold(fresh, 'pi_fresh')
        with mock.patch(
            'stripe.PaymentIntent.capture', return_value=_intent(status='succeeded')
        ) as capture:
            self.assertEqual(release_stale_authorizations(), 1)
        capture.assert_called_once_with('pi_old', idempotency_key=mock.ANY)

    def test_the_merchant_may_release_it_instead(self):
        from plugins.installed.payments.tasks import release_stale_authorizations

        self._mode('manual')
        self.payments.set_config('authorization_expiry', 'release')
        self.payments.set_config('authorization_days', 2)
        order = self._order()
        self._age(self._hold(order)[1], 3)
        with mock.patch(
            'stripe.PaymentIntent.cancel', return_value=_intent(status='canceled')
        ) as cancel:
            self.assertEqual(release_stale_authorizations(), 1)
        cancel.assert_called_once_with('pi_held')

    def test_the_days_never_exceed_what_the_card_holds(self):
        from plugins.installed.payments.services.capture import authorization_days

        for stored, expected in ((30, 6), (0, 1), ('x', 6), (3, 3)):
            with self.subTest(stored=stored):
                self.payments.set_config('authorization_days', stored)
                self.assertEqual(authorization_days(), expected)

    def test_the_sweep_is_scheduled_by_its_registered_name(self):
        from django.conf import settings

        entry = settings.CELERY_BEAT_SCHEDULE['payments:release_stale_authorizations']
        self.assertEqual(entry['task'], 'payments.release_stale_authorizations')


class HeldOrderGuardTests(CaptureTestBase):
    def test_an_unshipped_held_order_is_not_expired(self):
        from plugins.installed.orders.models import Order
        from plugins.installed.orders.tasks import expire_pending_orders

        order = self._order()
        Order.objects.filter(pk=order.pk).update(
            payment_status='authorized', placed_at=timezone.now() - timezone.timedelta(days=1)
        )
        expire_pending_orders()
        order = _fresh(order)
        self.assertEqual(order.status, 'pending')

    def test_a_held_order_cannot_be_refunded(self):
        from plugins.installed.orders.refunds import RefundService

        self._mode('manual')
        order = self._order()
        order, _ = self._hold(order)
        with self.assertRaisesMessage(ValueError, 'only authorized, not charged yet'):
            RefundService.process(order=order, amount=Money(5, 'USD'))
        self.assertFalse(order.refunds.exists())

    def test_a_held_order_is_never_marked_paid_by_hand(self):
        from plugins.installed.admin_dashboard.views_split.orders import _mark_order_paid

        self._mode('manual')
        order = self._order()
        order, _ = self._hold(order)
        self.assertFalse(_mark_order_paid(order))
        order = _fresh(order)
        self.assertEqual(order.payment_status, 'authorized')


class ChargeButtonTests(CaptureTestBase):
    def setUp(self):
        super().setUp()
        self._mode('manual')
        self.order = self._order()
        self.order, self.tx = self._hold(self.order)
        self.url = reverse('payments_dashboard:capture', args=[self.order.order_number])

    def _staff(self, **extra):
        user = get_user_model().objects.create_user(
            username=f'staff{get_user_model().objects.count()}',
            email='s@example.com',
            password='x',
            **extra,
        )
        self.client.force_login(user)
        return user

    def test_anonymous_is_sent_to_sign_in(self):
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertNotIn('/dashboard/orders/', response['Location'])
        self.tx.refresh_from_db()
        self.assertEqual(self.tx.status, Status.AUTHORIZED)

    def test_a_customer_cannot_charge(self):
        self._staff()
        self.client.post(self.url)
        self.tx.refresh_from_db()
        self.assertEqual(self.tx.status, Status.AUTHORIZED)

    def test_staff_charge_it_and_the_panel_shows_the_hold(self):
        self._staff(is_staff=True, is_superuser=True)
        page = self.client.get(
            reverse('admin_dashboard:order_detail', args=[self.order.order_number])
        )
        self.assertContains(page, 'data-payment-panel')
        self.assertContains(page, 'Charge now')
        self.assertNotContains(page, 'Mark as paid')
        with mock.patch('stripe.PaymentIntent.capture', return_value=_intent(status='succeeded')):
            response = self.client.post(self.url)
        self.assertEqual(response.status_code, 302)
        self.tx.refresh_from_db()
        self.assertEqual(self.tx.status, Status.SUCCEEDED)

    def test_get_is_refused(self):
        self._staff(is_staff=True, is_superuser=True)
        self.assertEqual(self.client.get(self.url).status_code, 405)


class CaptureToolTests(CaptureTestBase):
    def test_the_tool_is_a_gated_money_operation(self):
        from plugins.installed.payments.agent_tools import capture_payment_tool

        self.assertTrue(capture_payment_tool.requires_approval)
        self.assertEqual(capture_payment_tool.scopes, ['orders.write'])

    def test_the_tool_charges_the_held_payment(self):
        from plugins.installed.payments.agent_tools import capture_payment_tool

        self._mode('manual')
        order = self._order()
        order, _ = self._hold(order)
        with mock.patch('stripe.PaymentIntent.capture', return_value=_intent(status='succeeded')):
            result = capture_payment_tool.invoke(
                {
                    'order_number': order.order_number,
                    'confirmed': True,
                    'hard_gate_ack': 'YES',
                    'echo': order.order_number,
                }
            )
        self.assertTrue(result.output['charged'])

    def test_nothing_held_is_an_error(self):
        from morpheus.core import ToolError
        from plugins.installed.payments.agent_tools import capture_payment_tool

        order = self._order()
        with self.assertRaisesMessage(ToolError, 'Nothing on this order is waiting'):
            capture_payment_tool.invoke(
                {
                    'order_number': order.order_number,
                    'confirmed': True,
                    'hard_gate_ack': 'YES',
                    'echo': order.order_number,
                }
            )


class HoldSafetyTests(CaptureTestBase):
    """A hold is charged only on an open order nothing has paid (review of v0.155.0)."""

    def _released(self):
        return mock.patch('stripe.PaymentIntent.cancel', return_value=_intent(status='canceled'))

    def _close(self, order, status='cancelled'):
        # Straight to the row: a cancel whose own release did not reach Stripe.
        type(order).objects.filter(pk=order.pk).update(status=status)
        return _fresh(order)

    def test_a_closed_order_is_never_charged_its_hold_is_given_back(self):
        from plugins.installed.payments.services.capture import capture_order

        self._mode('manual')
        for status in ('cancelled', 'refunded'):
            order, tx = self._hold(self._order(), intent_id=f'pi_{status}')
            order = self._close(order, status)
            with (
                mock.patch('stripe.PaymentIntent.capture') as capture,
                self._released() as cancel,
            ):
                result = capture_order(order)
            self.assertFalse(result['success'])
            capture.assert_not_called()
            cancel.assert_called_once_with(f'pi_{status}')
            tx.refresh_from_db()
            self.assertEqual(tx.status, Status.RELEASED)

    def test_the_sweep_gives_back_a_closed_orders_hold_whatever_its_age(self):
        from plugins.installed.payments.tasks import release_stale_authorizations

        self._mode('manual')
        order, _ = self._hold(self._order())
        self._close(order)
        with (
            mock.patch('stripe.PaymentIntent.capture') as capture,
            self._released() as cancel,
        ):
            self.assertEqual(release_stale_authorizations(), 1)
        capture.assert_not_called()
        cancel.assert_called_once_with('pi_held')

    def test_a_card_held_after_the_order_was_cancelled_is_given_back(self):
        from plugins.installed.payments.services.stripe import PaymentService

        self._mode('manual')
        order = self._order()
        self._start(order)
        order = self._close(order)
        with self._released() as cancel, self.captureOnCommitCallbacks(execute=True):
            PaymentService._mark_transaction_authorized('pi_held')
        cancel.assert_called_once_with('pi_held')
        order = _fresh(order)
        self.assertEqual(order.status, 'cancelled')
        self.assertNotEqual(order.payment_status, 'authorized')
        tx = PaymentTransaction.objects.get(provider_transaction_id='pi_held')
        self.assertEqual(tx.status, Status.RELEASED)

    def test_a_second_hold_on_a_paid_order_is_given_back(self):
        from plugins.installed.payments.services.capture import capture_order
        from plugins.installed.payments.services.stripe import PaymentService

        self._mode('manual')
        order, _ = self._hold(self._order(), 'pi_a')
        with mock.patch('stripe.PaymentIntent.capture', return_value=_intent(status='succeeded')):
            self.assertTrue(capture_order(order)['success'])
        self._start(_fresh(order), 'pi_b')
        with self._released() as cancel, self.captureOnCommitCallbacks(execute=True):
            PaymentService._mark_transaction_authorized('pi_b')
        cancel.assert_called_once_with('pi_b')
        self.assertEqual(_fresh(order).payment_status, 'paid')

    def test_a_second_hold_on_a_held_order_is_given_back_and_the_first_still_counts(self):
        from plugins.installed.payments.order_panel import order_panel
        from plugins.installed.payments.services.capture import capture_order
        from plugins.installed.payments.services.stripe import PaymentService

        self._mode('manual')
        order, first = self._hold(self._order(), 'pi_a')
        self._start(order, 'pi_b')
        with self._released() as cancel, self.captureOnCommitCallbacks(execute=True):
            PaymentService._mark_transaction_authorized('pi_b')
        cancel.assert_called_once_with('pi_b')
        order = _fresh(order)
        self.assertEqual(order.payment_status, 'authorized')
        (panel,) = order_panel([], order=order)
        self.assertIn('Held', panel['html'])
        with mock.patch(
            'stripe.PaymentIntent.capture', return_value=_intent(status='succeeded')
        ) as capture:
            self.assertTrue(capture_order(order)['success'])
        capture.assert_called_once_with('pi_a', idempotency_key=f'capture-{first.pk}')

    def test_one_charge_at_a_time(self):
        from django.core.cache import cache

        from plugins.installed.payments.services.capture import capture_order

        self._mode('manual')
        order, tx = self._hold(self._order())
        cache.add(f'payments:capture:{tx.pk}', 1, 60)
        self.addCleanup(cache.delete, f'payments:capture:{tx.pk}')
        with mock.patch('stripe.PaymentIntent.capture') as capture:
            self.assertIn('already being charged', capture_order(order)['error'])
        capture.assert_not_called()
        self.assertFalse(order.events.filter(event_type='PAYMENT_CAPTURE_FAILED').exists())

    def test_a_completing_parcel_schedules_one_charge(self):
        self._mode('all_shipped')
        order, _ = self._hold(self._order())
        with mock.patch('plugins.installed.payments.tasks.capture_held_payment.delay') as delay:
            self._ship(order)
        delay.assert_called_once_with(str(order.pk))

    def test_the_hold_clock_is_when_stripe_authorized_it(self):
        from datetime import UTC, datetime

        from plugins.installed.payments.services.stripe import PaymentService, _event_time

        self._mode('manual')
        order = self._order()
        self._start(order)
        event = SimpleNamespace(
            id='evt_late',
            type='payment_intent.amount_capturable_updated',
            created=1_700_000_000,
            data=SimpleNamespace(object=SimpleNamespace(id='pi_held')),
            to_dict=lambda: {'id': 'evt_late'},
        )
        with mock.patch('stripe.Webhook.construct_event', return_value=event):
            PaymentService.process_webhook(b'{}', 'sig')
        tx = PaymentTransaction.objects.get(provider_transaction_id='pi_held')
        self.assertEqual(tx.authorized_at, datetime.fromtimestamp(1_700_000_000, tz=UTC))
        self.assertIsNone(_event_time('soon'))

    def test_a_release_is_on_the_timeline_once_with_its_reason(self):
        self._mode('manual')
        order, _ = self._hold(self._order())
        with self._released(), self.captureOnCommitCallbacks(execute=True):
            order.cancel(reason='Customer asked')
            order.save()
        (event,) = order.events.filter(event_type='PAYMENT_RELEASED')
        self.assertIn('cancelled', event.message)

    def test_a_parcel_never_writes_back_a_payment_taken_meanwhile(self):
        from plugins.installed.orders.fulfilment import create_fulfillment

        self._mode('manual')
        order, _ = self._hold(self._order(), 'pi_a')
        stale = _fresh(order)
        type(order).objects.filter(pk=order.pk).update(payment_status='paid')
        with self.captureOnCommitCallbacks(execute=True):
            create_fulfillment(stale)
        self.assertEqual(_fresh(order).payment_status, 'paid')

    def test_a_download_waits_for_the_charge_even_once_the_rest_ships(self):
        from plugins.installed.digital_products.library import is_delivered

        self._mode('manual')
        order, _ = self._hold(self._order((self.mug, 1), (self.ebook, 1)))
        type(order).objects.filter(pk=order.pk).update(status='shipped')
        self.assertFalse(is_delivered(_fresh(order)))
        type(order).objects.filter(pk=order.pk).update(payment_status='released')
        self.assertFalse(is_delivered(_fresh(order)))
        type(order).objects.filter(pk=order.pk).update(payment_status='paid')
        self.assertTrue(is_delivered(_fresh(order)))

    def test_nothing_charged_cannot_be_paid_back(self):
        from plugins.installed.orders.refunds import RefundService

        self._mode('manual')
        order, _ = self._hold(self._order())
        with self.assertRaisesMessage(ValueError, 'only authorized'):
            RefundService.record_external(order=order)
        type(order).objects.filter(pk=order.pk).update(payment_status='released')
        with self.assertRaisesMessage(ValueError, 'never charged'):
            RefundService.process(order=_fresh(order), amount=Money(5, 'USD'), settle='external')
        with self.assertRaisesMessage(ValueError, 'never charged'):
            RefundService.record_external(order=_fresh(order))
