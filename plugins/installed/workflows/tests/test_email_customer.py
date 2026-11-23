"""C2 — the "Email customer" action: service mail to whoever the event names,
marketing mail only to a confirmed newsletter subscriber."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from djmoney.money import Money

from plugins.installed.newsletter.models import NewsletterSubscriber
from plugins.installed.orders.models import Order
from plugins.installed.workflows.engine import run_workflow
from plugins.installed.workflows.models import Workflow

User = get_user_model()
LAYOUT_MARKER = 'class="preheader"'


def _html(msg) -> str:
    return next(body for body, kind in msg.alternatives if kind == 'text/html')


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    DEFAULT_FROM_EMAIL='shop@example.com',
    EMAIL_HOST='smtp.test',
)
class EmailCustomerTests(TestCase):
    def _run(self, payload, **spec):
        action = {'kind': 'email_customer', 'purpose': 'service', 'subject': 'Hello', 'body': 'Hi'}
        action.update(spec)
        wf = Workflow.objects.create(name='wf', trigger='order.paid', actions=[action])
        run = run_workflow(wf, payload)
        return run.actions_taken[0]

    def _order(self, **kw):
        defaults = {
            'email': 'g@x.com',
            'order_number': '1001',
            'subtotal': Money(20, 'USD'),
            'total': Money(20, 'USD'),
        }
        defaults.update(kw)
        return Order.objects.create(**defaults)

    def test_service_email_reaches_a_guest_order(self):
        order = self._order()
        done = self._run(
            {'order': order},
            subject='Order {order_number}',
            body='Hi {customer_name},\n\nOrder {order_number} is late.',
        )
        self.assertTrue(done['ok'], done)
        self.assertEqual(len(mail.outbox), 1)
        msg = mail.outbox[0]
        self.assertEqual((msg.to, msg.subject), (['g@x.com'], 'Order 1001'))
        html = _html(msg)
        self.assertIn('Order 1001 is late.', html)
        self.assertIn('Hi g,', html)
        self.assertIn(LAYOUT_MARKER, html)
        self.assertNotIn('List-Unsubscribe', msg.extra_headers)

    def test_the_customer_comes_before_the_order_email(self):
        customer = User.objects.create_user(
            username='ann', email='ann@x.com', password='x', first_name='Ann'
        )
        order = self._order(customer=customer, email='other@x.com')
        self._run({'order': order}, body='Dear {customer_first_name}')
        self.assertEqual(mail.outbox[0].to, ['ann@x.com'])
        self.assertIn('Dear Ann', mail.outbox[0].body)

    def test_placeholders_never_read_attributes(self):
        body = '{customer.user.password} {order.customer} {unknown}'
        self._run({'order': self._order()}, body=body)
        self.assertIn(body, mail.outbox[0].body)

    def test_body_html_is_escaped(self):
        self._run({'order': self._order()}, body='<script>x</script>')
        html = _html(mail.outbox[0])
        self.assertNotIn('<script>x', html)
        self.assertIn('&lt;script&gt;', html)

    def test_marketing_email_needs_a_confirmed_subscriber(self):
        done = self._run({'email': 'nobody@x.com'}, purpose='marketing')
        self.assertEqual((done['ok'], done['message']), (False, 'not a newsletter subscriber'))
        NewsletterSubscriber.objects.create(email='gone@x.com', status='unsubscribed')
        done = self._run({'email': 'gone@x.com'}, purpose='marketing')
        self.assertEqual(done['message'], 'not a newsletter subscriber')
        self.assertEqual(mail.outbox, [])

    def test_marketing_email_to_subscriber_carries_unsubscribe(self):
        sub = NewsletterSubscriber.objects.create(email='Sub@X.com', status='confirmed')
        customer = User.objects.create_user(username='sub', email='sub@x.com', password='x')
        done = self._run({'customer': customer}, purpose='marketing')
        self.assertTrue(done['ok'], done)
        msg = mail.outbox[0]
        self.assertIn(sub.confirm_token, msg.extra_headers['List-Unsubscribe'])
        self.assertIn(sub.confirm_token, _html(msg))

    def test_marketing_refused_when_the_order_refused_marketing(self):
        NewsletterSubscriber.objects.create(email='g@x.com', status='confirmed')
        order = self._order(
            metadata={'consent': {'managed': True, 'analytics': True, 'marketing': False}}
        )
        done = self._run({'order': order}, purpose='marketing')
        self.assertEqual(done['message'], 'the order refused marketing')
        self.assertEqual(mail.outbox, [])

    def test_missing_purpose_fails_with_a_message(self):
        done = self._run({'order': self._order()}, purpose='')
        self.assertEqual(done['message'], 'purpose must be service or marketing')

    def test_missing_subject_fails_with_a_message(self):
        done = self._run({'order': self._order()}, subject=' ')
        self.assertEqual(done['message'], 'no subject or body')

    def test_no_address_fails_with_a_message(self):
        done = self._run({})
        self.assertEqual(done['message'], 'no email address in the event')

    @override_settings(EMAIL_HOST='')
    def test_no_sending_email_fails_with_a_message(self):
        done = self._run({'order': self._order()})
        self.assertEqual((done['ok'], done['message']), (False, 'no sending email'))
        self.assertEqual(mail.outbox, [])


class PayloadSnapshotTests(TestCase):
    def test_a_model_in_the_payload_is_recorded_as_a_placeholder(self):
        order = Order.objects.create(
            email='g@x.com', subtotal=Money(1, 'USD'), total=Money(1, 'USD')
        )
        wf = Workflow.objects.create(name='wf', trigger='order.paid', actions=[])
        run = run_workflow(wf, {'order': order, 'note': 'kept'})
        run.refresh_from_db()
        self.assertEqual(run.payload, {'order': '<Order>', 'note': 'kept'})
