"""The withdrawal function (EU Consumer Rights Directive, Art. 11a; v0.181.0).

"Withdraw from contract here": a form (name, order number, email), then a page
that repeats it with a "Confirm withdrawal" button; an acknowledgement by email
with the date and time; the same last page whether or not the details named an
order. The rule is orders' (``orders.withdrawal``): lines with no right are
listed with the reason, the period runs from delivery for goods and from the
order for digital content, an order none of which has left is cancelled and
paid back in full, and anything else becomes a return.
"""

# ruff: noqa: PLC0415
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone
from djmoney.money import Money

from core.hooks import MorpheusEvents, hook_registry
from plugins.installed.catalog.models import Product
from plugins.installed.orders import withdrawal as rule
from plugins.installed.orders.models import Fulfillment, Order, OrderItem, Refund, WithdrawalNotice
from plugins.testing import set_app_settings

_PROCESS = 'plugins.installed.orders.refunds.RefundService.process'
_ON = {'withdrawal_function': True}


def _usd(n):
    return Money(Decimal(str(n)), 'USD')


def _product(slug, **kw):
    return Product.objects.create(name=slug.title(), slug=slug, sku=slug.upper(), price=10, **kw)


def _order(*lines, status='pending', payment_status='unpaid', email='buyer@example.com', **kw):
    order = Order.objects.create(
        email=email, subtotal=_usd(20), total=_usd(20), payment_status=payment_status, **kw
    )
    for product in lines:
        OrderItem.objects.create(
            order=order,
            product=product,
            product_name=product.name,
            quantity=1,
            unit_price=_usd(10),
            total_price=_usd(10),
        )
    if status != 'pending':
        Order.objects.filter(pk=order.pk).update(status=status)
        order = Order.objects.get(pk=order.pk)
    return order


def _paid_back(order=None, amount=None, **kw):
    return Refund.objects.create(order=order, amount=amount, is_processed=True)


class _Base(TestCase):
    def setUp(self):
        cache.clear()  # the rate limit counts per address in the cache
        # Names no theme's own copy contains (CLAUDE.md: never assert a bare display word).
        self.book = _product('zephyr-lamp')
        self.ebook = _product('quillon-ebook', product_type='digital', requires_shipping=False)

    def switch_on(self, **values):
        set_app_settings(self, 'returns_portal', **{**_ON, **values})

    def submit(self, number, email, name='Ana Kovač'):
        self.client.post('/withdraw/', {'name': name, 'order_number': number, 'email': email})
        # The acknowledgement goes after commit (ORDER_WITHDRAWAL_REQUESTED).
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post('/withdraw/confirm/', follow=True)


class SwitchTests(_Base):
    def test_the_pages_are_gone_while_the_function_is_off(self):
        for url in ('/withdraw/', '/withdraw/sent/'):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.post('/withdraw/confirm/').status_code, 404)

    def test_the_period_is_never_under_fourteen_days(self):
        from plugins.installed.returns_portal import withdrawal

        self.switch_on(withdrawal_days=7)
        self.assertEqual(withdrawal.days(), 14)
        self.switch_on(withdrawal_days=30)
        self.assertEqual(withdrawal.days(), 30)


class TwoStepTests(_Base):
    def setUp(self):
        super().setUp()
        self.switch_on()
        self.order = _order(self.book)

    def test_the_first_step_records_nothing(self):
        page = self.client.post(
            '/withdraw/',
            {'name': 'Ana', 'order_number': self.order.order_number, 'email': 'buyer@example.com'},
        )
        self.assertEqual(page.status_code, 200)
        html = page.content.decode()
        self.assertIn('Confirm withdrawal', html)
        self.assertIn(self.order.order_number, html)
        self.assertFalse(WithdrawalNotice.objects.exists())
        self.assertEqual(len(mail.outbox), 0)

    def test_confirming_records_it_and_acknowledges_it(self):
        page = self.submit(self.order.order_number, 'BUYER@example.com')
        self.assertEqual(page.status_code, 200)
        notice = WithdrawalNotice.objects.get(order=self.order)
        self.assertEqual(notice.name, 'Ana Kovač')
        self.assertIn(
            f'withdraw from my contract for order {self.order.order_number}', notice.statement
        )
        self.assertIsNotNone(notice.acknowledged_at)
        # The acknowledgement, and the cancellation email the cancel sends.
        acks = [m for m in mail.outbox if m.subject.startswith('We received your withdrawal')]
        self.assertEqual(len(acks), 1)
        sent = acks[0]
        self.assertEqual(sent.to, ['BUYER@example.com'])
        self.assertIn(notice.statement, sent.body)
        stamp = timezone.localtime(notice.submitted_at)
        self.assertIn(f'Received on {stamp:%-d %B %Y, %H:%M}', sent.body)
        event = self.order.events.filter(event_type='ORDER_WITHDRAWAL').get()
        self.assertIn('Ana Kovač withdrew from the contract', event.message)

    def test_a_missing_field_or_a_bad_email_stays_on_the_form(self):
        for data in (
            {'name': '', 'order_number': self.order.order_number, 'email': 'buyer@example.com'},
            {'name': 'Ana', 'order_number': self.order.order_number, 'email': 'not-an-email'},
        ):
            with self.subTest(data=data):
                page = self.client.post('/withdraw/', data)
                self.assertNotIn('Confirm withdrawal', page.content.decode())
                self.assertIn('role="alert"', page.content.decode())

    def test_confirming_without_the_first_step_goes_back_to_it(self):
        page = self.client.post('/withdraw/confirm/')
        self.assertRedirects(page, '/withdraw/')

    def test_the_bot_check_is_asked(self):
        saved = list(hook_registry._handlers.get(MorpheusEvents.BOT_CHECK_PASSES, []))
        self.addCleanup(hook_registry._handlers.__setitem__, MorpheusEvents.BOT_CHECK_PASSES, saved)
        hook_registry.register(
            MorpheusEvents.BOT_CHECK_PASSES, lambda value, form='', **kw: form != 'withdrawal'
        )
        page = self.client.post(
            '/withdraw/',
            {'name': 'Ana', 'order_number': self.order.order_number, 'email': 'buyer@example.com'},
        )
        self.assertNotIn('Confirm withdrawal', page.content.decode())
        self.assertIsNone(self.client.session.get('withdrawal_draft'))

    def test_an_address_gets_ten_tries_an_hour(self):
        data = {'name': 'Ana', 'order_number': 'MRP00000000', 'email': 'x@example.com'}
        for _ in range(10):
            self.assertIn(
                'Confirm withdrawal', self.client.post('/withdraw/', data).content.decode()
            )
        refused = self.client.post('/withdraw/', data).content.decode()
        self.assertIn('Too many tries', refused)


class GuestLookupTests(_Base):
    """A guest learns nothing about an order: the last page reads the same either way."""

    def setUp(self):
        super().setUp()
        self.switch_on()
        self.order = _order(self.book)

    def test_the_answer_is_the_same_whether_or_not_the_details_match(self):
        wrong = self.submit(self.order.order_number, 'someone-else@example.com')
        self.assertFalse(WithdrawalNotice.objects.exists())
        self.assertEqual(len(mail.outbox), 0)
        right = self.submit(self.order.order_number, 'buyer@example.com')
        self.assertEqual(WithdrawalNotice.objects.count(), 1)
        main = lambda page: page.content.decode().split('<section', 1)[1].split('</section>')[0]  # noqa: E731
        self.assertEqual(main(wrong), main(right))
        self.assertNotIn(self.order.order_number, main(right))

    def test_the_confirm_page_shows_a_guest_no_order_contents(self):
        page = self.client.post(
            '/withdraw/',
            {'name': 'Ana', 'order_number': self.order.order_number, 'email': 'buyer@example.com'},
        )
        self.assertNotIn('Zephyr', page.content.decode())


class IdentifiedTests(_Base):
    """The owner (their account) and the order email's link see the lines."""

    def setUp(self):
        super().setUp()
        self.switch_on()
        user_model = get_user_model()
        self.buyer = user_model.objects.create_user(
            username='buyer', email='buyer@example.com', password='pw-12345'
        )
        self.other = user_model.objects.create_user(
            username='other', email='other@example.com', password='pw-12345'
        )
        self.order = _order(self.book, customer=self.buyer)

    def _confirm_page(self):
        return self.client.post(
            '/withdraw/',
            {'name': 'Ana', 'order_number': self.order.order_number, 'email': 'buyer@example.com'},
        ).content.decode()

    def test_the_owner_sees_the_lines(self):
        self.client.force_login(self.buyer)
        form = self.client.get(f'/withdraw/?order={self.order.order_number}').content.decode()
        self.assertIn(f'value="{self.order.order_number}"', form)
        self.assertIn('Can be withdrawn', self._confirm_page())

    def test_the_order_emails_link_identifies_the_order(self):
        url = f'/withdraw/?order={self.order.order_number}&token={self.order.public_token}'
        self.assertIn('value="buyer@example.com"', self.client.get(url).content.decode())
        self.assertIn('Can be withdrawn', self._confirm_page())

    def test_another_customer_or_a_wrong_token_is_not_identified(self):
        self.client.force_login(self.other)
        form = self.client.get(f'/withdraw/?order={self.order.order_number}').content.decode()
        self.assertNotIn(f'value="{self.order.order_number}"', form)
        self.client.logout()
        self.client.get(f'/withdraw/?order={self.order.order_number}&token=wrong')
        self.assertNotIn('Can be withdrawn', self._confirm_page())

    def test_the_owner_sees_what_happened(self):
        self.client.force_login(self.buyer)
        self.client.get(f'/withdraw/?order={self.order.order_number}')
        page = self.submit(self.order.order_number, 'buyer@example.com').content.decode()
        self.assertIn(f'from order {self.order.order_number}', page)
        self.assertIn('The order is cancelled', page)


class LineRightTests(_Base):
    def test_a_dated_service_has_no_right(self):
        stay = _product('stay', product_type='service', requires_shipping=False)
        rights = rule.line_rights(_order(stay), days=14)
        self.assertFalse(rights[0].right)
        self.assertEqual(rights[0].reason, rule.REASON_SERVICE)

    def test_a_waived_download_loses_the_right_once_paid(self):
        waiver = {'digital_withdrawal_waiver': {'accepted': True, 'text': 'x', 'at': 'now'}}
        unpaid = _order(self.ebook, metadata=waiver)
        self.assertTrue(rule.line_rights(unpaid, days=14)[0].right)
        paid = _order(self.ebook, payment_status='paid', metadata=waiver)
        right = rule.line_rights(paid, days=14)[0]
        self.assertFalse(right.right)
        self.assertEqual(right.reason, rule.REASON_WAIVED)

    def test_a_download_without_the_waiver_keeps_the_right_for_the_period(self):
        order = _order(self.ebook, payment_status='paid')
        self.assertTrue(rule.line_rights(order, days=14)[0].right)
        later = timezone.localdate() + timedelta(days=15)
        closed = rule.line_rights(order, days=14, today=later)[0]
        self.assertFalse(closed.right)
        self.assertIn('The withdrawal period ended on', closed.reason)

    def test_the_period_for_goods_runs_from_delivery(self):
        order = _order(self.book, status='delivered', payment_status='paid')
        Fulfillment.objects.create(
            order=order,
            status='delivered',
            shipped_at=timezone.now() - timedelta(days=25),
            delivered_at=timezone.now() - timedelta(days=20),
        )
        self.assertFalse(rule.line_rights(order, days=14)[0].right)
        self.assertTrue(rule.line_rights(order, days=30)[0].right)

    def test_goods_still_to_leave_keep_the_period_open(self):
        order = _order(self.book, status='processing', payment_status='paid')
        Order.objects.filter(pk=order.pk).update(placed_at=timezone.now() - timedelta(days=90))
        right = rule.line_rights(Order.objects.get(pk=order.pk), days=14)[0]
        self.assertTrue(right.right)
        self.assertIsNone(right.ends)

    def test_with_no_delivery_recorded_the_period_allows_for_transit(self):
        order = _order(self.book, status='shipped', payment_status='paid')
        Fulfillment.objects.create(
            order=order, status='shipped', shipped_at=timezone.now() - timedelta(days=40)
        )
        self.assertTrue(rule.line_rights(order, days=14)[0].right)
        Fulfillment.objects.filter(order=order).update(
            shipped_at=timezone.now() - timedelta(days=50)
        )
        self.assertFalse(rule.line_rights(order, days=14)[0].right)


class OutcomeTests(_Base):
    def setUp(self):
        super().setUp()
        self.switch_on()

    def test_an_order_none_of_which_has_left_is_cancelled_and_paid_back_whatever_the_settings(self):
        # Neither cancel setting applies to a withdrawal: the law gives the right.
        set_app_settings(self, 'orders', customer_cancel_paid='contact', staff_cancel_refund='keep')
        order = _order(self.book, status='processing', payment_status='paid')
        with mock.patch(_PROCESS, side_effect=_paid_back) as process:
            self.submit(order.order_number, 'buyer@example.com')
        self.assertEqual(Order.objects.get(pk=order.pk).status, 'cancelled')
        self.assertEqual(process.call_args.kwargs['amount'], _usd(20))
        self.assertEqual(process.call_args.kwargs['settle'], '')
        notice = WithdrawalNotice.objects.get(order=order)
        self.assertEqual(notice.outcome, 'cancelled')
        self.assertIsNotNone(notice.refund)

    def test_a_shipped_order_becomes_a_return(self):
        order = _order(self.book, status='shipped', payment_status='paid')
        Fulfillment.objects.create(order=order, status='shipped', shipped_at=timezone.now())
        with mock.patch(_PROCESS) as process:
            self.submit(order.order_number, 'buyer@example.com')
        process.assert_not_called()
        notice = WithdrawalNotice.objects.get(order=order)
        self.assertEqual(notice.outcome, 'return_requested')
        self.assertEqual(notice.return_request.reason, 'withdrawal')
        self.assertEqual(Order.objects.get(pk=order.pk).status, 'shipped')

    def test_lines_without_a_right_are_listed_and_left_out(self):
        waiver = {'digital_withdrawal_waiver': {'accepted': True, 'text': 'x', 'at': 'now'}}
        order = _order(
            self.book, self.ebook, status='processing', payment_status='paid', metadata=waiver
        )
        self.submit(order.order_number, 'buyer@example.com')
        notice = WithdrawalNotice.objects.get(order=order)
        self.assertEqual(notice.outcome, 'return_requested')
        self.assertEqual(len(notice.return_request.items), 1)
        reasons = {line['product_name']: line['reason'] for line in notice.lines}
        self.assertEqual(reasons['Quillon-Ebook'], rule.REASON_WAIVED)
        self.assertIn(
            f'Not withdrawn: {rule.REASON_WAIVED}'[:40], mail.outbox[0].alternatives[0][0]
        )

    def test_nothing_to_withdraw_is_still_acknowledged(self):
        waiver = {'digital_withdrawal_waiver': {'accepted': True, 'text': 'x', 'at': 'now'}}
        order = _order(self.ebook, payment_status='paid', metadata=waiver)
        self.submit(order.order_number, 'buyer@example.com')
        notice = WithdrawalNotice.objects.get(order=order)
        self.assertEqual(notice.outcome, 'nothing')
        self.assertEqual(len(mail.outbox), 1)

    def test_a_withdrawal_while_another_is_acted_on_does_nothing_more(self):
        # A double click on "Confirm withdrawal": the first notice is still 'received'.
        order = _order(self.book, status='shipped', payment_status='paid')
        Fulfillment.objects.create(order=order, status='shipped', shipped_at=timezone.now())
        WithdrawalNotice.objects.create(order=order, name='Ana', email='buyer@example.com')
        self.submit(order.order_number, 'buyer@example.com')
        self.assertEqual(order.return_requests.count(), 0)
        notice = WithdrawalNotice.objects.order_by('-submitted_at').first()
        self.assertEqual(notice.outcome, 'already')

    def test_an_order_cancelled_meanwhile_opens_no_return(self):
        from plugins.installed.orders.cancellation import CancelRefused  # noqa: PLC0415

        order = _order(self.book, status='processing', payment_status='paid')

        def cancelled_first(o, **kw):
            Order.objects.filter(pk=o.pk).update(status='cancelled')
            raise CancelRefused('cancelled')

        with mock.patch(
            'plugins.installed.orders.cancellation.cancel_with_refund', side_effect=cancelled_first
        ):
            self.submit(order.order_number, 'buyer@example.com')
        self.assertEqual(order.return_requests.count(), 0)
        self.assertEqual(WithdrawalNotice.objects.get(order=order).outcome, 'already')

    def test_a_second_withdrawal_opens_no_second_return(self):
        order = _order(self.book, status='shipped', payment_status='paid')
        Fulfillment.objects.create(order=order, status='shipped', shipped_at=timezone.now())
        self.submit(order.order_number, 'buyer@example.com')
        self.submit(order.order_number, 'buyer@example.com')
        self.assertEqual(order.return_requests.count(), 1)
        self.assertEqual(
            list(
                WithdrawalNotice.objects.order_by('submitted_at').values_list('outcome', flat=True)
            ),
            ['return_requested', 'already'],
        )


class LinkTests(_Base):
    def test_the_order_email_links_the_function_only_while_it_is_on(self):
        from core.emails.handlers import on_order_placed

        order = _order(self.book)
        on_order_placed(order)
        self.assertNotIn('Withdraw from contract here', mail.outbox[-1].body)
        self.switch_on()
        on_order_placed(order)
        body = mail.outbox[-1].body
        self.assertIn('Withdraw from contract here', body)
        self.assertIn(f'/withdraw/?order={order.order_number}&token={order.public_token}', body)

    def test_the_footer_links_the_function_only_while_it_is_on(self):
        self.assertNotIn('href="/withdraw/"', self.client.get('/').content.decode())
        self.switch_on()
        self.assertIn('href="/withdraw/"', self.client.get('/').content.decode())


@override_settings(SECURE_SSL_REDIRECT=False)
class StoreChecksTests(_Base):
    def _country(self, code):
        from core.models import StoreSettings

        store = StoreSettings.objects.first() or StoreSettings.objects.create()
        store.country = code
        store.save()

    def test_a_store_in_the_eu_is_told_while_the_function_is_off(self):
        from plugins.installed.returns_portal import withdrawal

        self._country('HR')
        steps = withdrawal.on_setup_steps([])
        checks = withdrawal.on_health_checks([])
        self.assertFalse(steps[0]['done'])
        self.assertFalse(checks[0]['ok'])
        self.switch_on()
        self.assertTrue(withdrawal.on_setup_steps([])[0]['done'])
        self.assertTrue(withdrawal.on_health_checks([])[0]['ok'])

    def test_a_store_outside_the_eea_is_not_asked(self):
        from plugins.installed.returns_portal import withdrawal

        self._country('US')
        self.assertEqual(withdrawal.on_setup_steps([]), [])
        self.assertEqual(withdrawal.on_health_checks([]), [])


class LindaToolTests(_Base):
    def setUp(self):
        super().setUp()
        self.switch_on()
        self.staff = get_user_model().objects.create_user(
            username='staff', email='staff@example.com', password='pw-12345', is_staff=True
        )

    def _tool(self, name):
        from core.agents.registry import agent_registry

        return agent_registry.get_tool(name)

    def test_both_tools_are_registered_and_the_write_needs_approval(self):
        self.assertIn('orders.read', self._tool('returns.list_withdrawals').scopes)
        write = self._tool('returns.process_withdrawal')
        self.assertTrue(write.requires_approval)
        self.assertIn('orders.write', write.scopes)

    def test_a_withdrawal_sent_by_email_is_recorded_and_listed(self):
        order = _order(self.book, status='shipped', payment_status='paid')
        Fulfillment.objects.create(order=order, status='shipped', shipped_at=timezone.now())
        result = self._tool('returns.process_withdrawal').invoke(
            {'order_number': order.order_number, 'name': 'Ana Kovač'},
            context={'user': self.staff},
        )
        self.assertEqual(result.output['outcome'], 'return_requested')
        notice = WithdrawalNotice.objects.get(order=order)
        self.assertEqual((notice.source, notice.email), ('staff', 'buyer@example.com'))
        listed = self._tool('returns.list_withdrawals').invoke({'order_number': order.order_number})
        self.assertEqual(listed.output['withdrawals'][0]['id'], str(notice.pk))

    def test_the_refund_cap_applies_before_anything_is_recorded(self):
        from core.agents.tools import ToolError

        order = _order(self.book, status='processing', payment_status='paid')
        with (
            mock.patch(
                'plugins.installed.returns_portal.agent_tools.max_refund_value', return_value=5
            ),
            self.assertRaises(ToolError),
        ):
            self._tool('returns.process_withdrawal').invoke(
                {'order_number': order.order_number, 'name': 'Ana'},
                context={'user': self.staff},
            )
        self.assertFalse(WithdrawalNotice.objects.exists())
        self.assertEqual(Order.objects.get(pk=order.pk).status, 'processing')
