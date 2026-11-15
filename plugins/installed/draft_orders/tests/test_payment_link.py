"""A draft can be sent to the customer as a link to pay it (A8, v0.171.0).

Until v0.171.0 a draft had no page a customer could open, so a quote was paid
outside the shop, and converting it left an order the unpaid-order sweep
cancelled an hour later.
"""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import Client, TestCase, override_settings
from djmoney.money import Money

from core.agents import agent_registry
from plugins.installed.draft_orders import services
from plugins.installed.draft_orders.models import DraftOrder, DraftOrderLine
from plugins.installed.orders.models import Order
from plugins.installed.orders.payment_deadline import waiting_for_payment


def _draft(email='buyer@example.com'):
    draft = DraftOrder.objects.create(customer_email=email)
    DraftOrderLine.objects.create(
        draft=draft, product_name='Signed Edition', sku='SE-1',
        unit_price=Money(Decimal('40.00'), 'USD'), quantity=1,
    )  # fmt: skip
    services.recalc(draft)
    return draft


@override_settings(DEFAULT_FROM_EMAIL='shop@example.com')
class SendPaymentLinkTests(TestCase):
    def test_an_open_draft_is_converted_and_the_link_emailed(self):
        draft = _draft()
        order = services.send_payment_link(draft)
        draft.refresh_from_db()
        self.assertEqual(draft.status, 'converted')
        self.assertEqual(draft.converted_order_id, str(order.pk))
        self.assertEqual(order.total.amount, Decimal('40.00'))
        link_emails = [m for m in mail.outbox if m.subject.startswith('Pay for order')]
        self.assertEqual(len(link_emails), 1)
        self.assertIn(f'/pay/{order.public_token}/', link_emails[0].body)
        self.assertTrue(order.events.filter(event_type='PAYMENT_LINK_SENT').exists())

    def test_a_converted_draft_sends_the_link_for_its_order_again(self):
        draft = _draft()
        first = services.send_payment_link(draft)
        again = services.send_payment_link(DraftOrder.objects.get(pk=draft.pk))
        self.assertEqual(again.pk, first.pk)
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(first.events.filter(event_type='PAYMENT_LINK_SENT').count(), 2)

    def test_no_email_changes_nothing(self):
        draft = _draft(email='')
        with self.assertRaises(services.PaymentLinkError):
            services.send_payment_link(draft)
        self.assertEqual(DraftOrder.objects.get(pk=draft.pk).status, 'draft')
        self.assertFalse(Order.objects.exists())

    def test_a_paid_order_gets_no_link(self):
        draft = _draft()
        order = services.convert_to_order(draft)
        Order.objects.filter(pk=order.pk).update(payment_status='paid')
        with self.assertRaisesMessage(services.PaymentLinkError, 'already paid'):
            services.send_payment_link(DraftOrder.objects.get(pk=draft.pk))

    def test_a_converted_draft_waits_for_payment(self):
        order = services.convert_to_order(_draft())
        self.assertTrue(waiting_for_payment(Order.objects.get(pk=order.pk)))


@override_settings(DEFAULT_FROM_EMAIL='shop@example.com')
class SendLinkViewTests(TestCase):
    def setUp(self):
        self.draft = _draft()
        self.url = f'/dashboard/draft-orders/{self.draft.number}/send-link/'

    def _client(self, *, staff):
        user = get_user_model().objects.create_user(
            username=f'u-{staff}', email=f'{staff}@example.com', password='x', is_staff=staff
        )
        client = Client()
        client.force_login(user)
        return client

    def test_anonymous_is_sent_away(self):
        response = Client().post(self.url)
        self.assertIn(response.status_code, (302, 403))
        self.assertFalse(Order.objects.exists())

    def test_a_customer_is_sent_away(self):
        response = self._client(staff=False).post(self.url)
        self.assertIn(response.status_code, (302, 403))
        self.assertFalse(Order.objects.exists())

    def test_staff_send_the_link(self):
        client = self._client(staff=True)
        response = client.post(self.url)
        self.assertRedirects(
            response, f'/dashboard/draft-orders/{self.draft.number}/', fetch_redirect_response=False
        )
        order = Order.objects.get()
        page = client.get(f'/dashboard/draft-orders/{self.draft.number}/').content.decode()
        self.assertIn(f'/pay/{order.public_token}/', page)
        self.assertIn(f'/dashboard/orders/{order.order_number}/', page)

    def test_a_get_sends_nothing(self):
        self._client(staff=True).get(self.url)
        self.assertFalse(Order.objects.exists())
        self.assertEqual(mail.outbox, [])


class SendPaymentLinkToolTests(TestCase):
    def test_the_tool_needs_the_merchants_yes(self):
        tool = agent_registry.get_tool('draft_orders.send_payment_link')
        self.assertIsNotNone(tool)
        self.assertTrue(tool.requires_approval)
        self.assertIn('orders.write', tool.scopes)

    @override_settings(DEFAULT_FROM_EMAIL='shop@example.com')
    def test_the_tool_sends_the_link(self):
        draft = _draft()
        result = agent_registry.get_tool('draft_orders.send_payment_link').handler(
            number=draft.number
        )
        order = Order.objects.get()
        self.assertEqual(result.output['order_number'], order.order_number)
        self.assertTrue(result.output['pay_url'].endswith(f'/pay/{order.public_token}/'))
