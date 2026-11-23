"""The post-purchase journey sends its emails (C1, v0.189.0).

Nothing sent them before: the task was never in the beat schedule. Now it is, each
step is a setting that starts off, a late step is skipped rather than sent, the
emails are ``core.emails`` templates to the order's address, and the review request
and the survey are marketing: consent-gated with a one-click unsubscribe.
"""

# ruff: noqa: PLC0415
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core import mail
from django.template.loader import get_template
from django.test import TestCase
from django.utils import timezone
from djmoney.money import Money

from plugins.installed.catalog.models import Product
from plugins.installed.orders.models import Order, OrderItem
from plugins.installed.post_purchase.models import JourneyStep
from plugins.installed.post_purchase.tasks import process_due_steps
from plugins.testing import set_app_settings

ALL_ON = {
    'delivered_followup_enabled': True,
    'review_request_enabled': True,
    'nps_survey_enabled': True,
}


def _usd(n):
    return Money(Decimal(n), 'USD')


class _Base(TestCase):
    def setUp(self):
        customer = get_user_model().objects.create_user(
            username='quillon', email='account@example.com', password='x'
        )
        self.order = Order.objects.create(
            customer=customer,
            email='quillon@example.com',
            subtotal=_usd(20),
            total=_usd(20),
            status='shipped',
            payment_status='paid',
        )
        book = Product.objects.create(
            name='Zephyr Atlas', slug='zephyr-atlas', sku='ZA', price=_usd(20)
        )
        OrderItem.objects.create(
            order=self.order,
            product=book,
            product_name=book.name,
            sku=book.sku,
            quantity=1,
            unit_price=book.price,
            total_price=book.price,
        )

    def due(self, step, *, ago=timedelta(minutes=5)):
        return JourneyStep.objects.create(order=self.order, step=step, due_at=timezone.now() - ago)

    def run_due(self):
        with self.captureOnCommitCallbacks(execute=True):
            return process_due_steps()

    def sent(self, words):
        return [m for m in mail.outbox if words in m.subject]

    def body(self, message):
        return message.alternatives[0][0] if message.alternatives else message.body


class ScheduleTests(_Base):
    def test_the_sender_is_in_the_beat_schedule_by_its_registered_name(self):
        from django.conf import settings

        entry = settings.CELERY_BEAT_SCHEDULE['post_purchase:process_due_steps']
        self.assertEqual(entry['task'], 'post_purchase.process_due_steps')
        self.assertEqual(entry['schedule'], 15 * 60)

    def test_every_step_starts_off(self):
        from plugins.installed.post_purchase.handlers import on_order_fulfilled

        on_order_fulfilled(order=self.order)
        self.assertFalse(JourneyStep.objects.filter(order=self.order).exists())

    def test_a_switched_on_step_is_scheduled_after_its_delay(self):
        from plugins.installed.post_purchase.handlers import on_order_fulfilled

        set_app_settings(self, 'post_purchase', review_request_enabled=True)
        set_app_settings(self, 'post_purchase', review_request_delay_days=3)
        on_order_fulfilled(order=self.order)
        step = JourneyStep.objects.get(order=self.order)
        self.assertEqual(step.step, 'review_request')
        self.assertAlmostEqual(
            step.due_at.timestamp(),
            (timezone.now() + timedelta(days=3)).timestamp(),
            delta=60,
        )

    def test_placing_an_order_schedules_no_tracking_email(self):
        from core.hooks import MorpheusEvents, hook_registry

        set_app_settings(self, 'post_purchase', **ALL_ON)
        hook_registry.fire(MorpheusEvents.ORDER_PLACED, order=self.order)
        self.assertFalse(JourneyStep.objects.filter(order=self.order).exists())


class ReviewFixTests(_Base):
    """Found by the review before merge (v0.189.0)."""

    def test_the_worker_sees_a_setting_saved_by_another_process(self):
        from plugins.installed.post_purchase.handlers import _config
        from plugins.models import PluginConfig
        from plugins.registry import app_registry

        plugin = app_registry.get('post_purchase')
        self.addCleanup(plugin.invalidate_config_cache)
        self.assertFalse(_config()['review_request_enabled'])  # warms this process's copy
        # The dashboard saves it in a web worker; this process only sees the row.
        PluginConfig.objects.update_or_create(
            plugin_name='post_purchase', defaults={'config': {'review_request_enabled': True}}
        )
        plugin._config_read_at -= 60
        self.assertTrue(_config()['review_request_enabled'])

    def test_the_arrival_check_waits_for_the_delivery(self):
        from plugins.installed.post_purchase.handlers import on_order_delivered, on_order_fulfilled

        set_app_settings(self, 'post_purchase', **ALL_ON)
        on_order_fulfilled(order=self.order)
        steps = set(JourneyStep.objects.filter(order=self.order).values_list('step', flat=True))
        self.assertEqual(steps, {'review_request', 'nps_survey'})
        on_order_delivered(order=self.order)
        self.assertTrue(
            JourneyStep.objects.filter(order=self.order, step='delivered_followup').exists()
        )

    def test_an_old_backlog_never_holds_up_a_step_that_is_due(self):
        set_app_settings(self, 'post_purchase', **ALL_ON)
        Order.objects.filter(pk=self.order.pk).update(
            metadata={'consent': {'managed': True, 'analytics': False, 'marketing': True}}
        )
        old = []
        for i in range(120):
            o = Order.objects.create(
                email=f'old{i}@example.com', subtotal=_usd(1), total=_usd(1), status='shipped'
            )
            old.append(
                JourneyStep(
                    order=o, step='tracking_sent', due_at=timezone.now() - timedelta(days=90)
                )
            )
        JourneyStep.objects.bulk_create(old)
        fresh = self.due('delivered_followup')
        self.run_due()
        fresh.refresh_from_db()
        self.assertEqual(fresh.status, 'sent')
        self.assertFalse(JourneyStep.objects.filter(status='queued').exists())


class DeliveryLedgerTests(_Base):
    """A step is ``sent`` only once its email went out (EMAIL_DELIVERED), so a
    broker that refuses the message leaves it to be tried again (Codex, PR #208)."""

    def setUp(self):
        super().setUp()
        set_app_settings(self, 'post_purchase', **ALL_ON)

    def refuse_delivery(self):
        from unittest import mock

        return mock.patch(
            'core.emails.tasks.deliver_email.delay', side_effect=ConnectionError('broker down')
        )

    def test_a_refused_email_is_not_recorded_as_sent(self):
        step = self.due('delivered_followup')
        with self.refuse_delivery():
            self.run_due()
        step.refresh_from_db()
        self.assertEqual(step.status, 'sending')
        self.assertIsNone(step.sent_at)

    def test_a_step_stuck_sending_is_tried_again_once(self):
        step = self.due('delivered_followup')
        with self.refuse_delivery():
            self.run_due()
        JourneyStep.objects.filter(pk=step.pk).update(
            updated_at=timezone.now() - timedelta(hours=2)
        )
        self.run_due()
        step.refresh_from_db()
        self.assertEqual(step.status, 'sent')
        self.assertEqual(len(self.sent('arrive')), 1)

    def test_a_second_failure_marks_it_failed(self):
        step = self.due('delivered_followup')
        for _ in range(3):
            with self.refuse_delivery():
                self.run_due()
            JourneyStep.objects.filter(pk=step.pk).update(
                updated_at=timezone.now() - timedelta(hours=2)
            )
        self.run_due()
        step.refresh_from_db()
        self.assertEqual((step.status, step.error), ('failed', 'not delivered'))
        self.assertEqual(mail.outbox, [])

    def test_a_store_without_a_sending_email_records_no_send(self):
        from core.hooks import MorpheusEvents, hook_registry

        step = self.due('delivered_followup')
        JourneyStep.objects.filter(pk=step.pk).update(status='sending')
        hook_registry.fire(
            MorpheusEvents.EMAIL_DELIVERED, tag=f'journey:{step.pk}', reached_inbox=False
        )
        step.refresh_from_db()
        self.assertEqual((step.status, step.error), ('failed', 'no sending email'))

    def test_delivery_confirms_the_send(self):
        step = self.due('delivered_followup')
        self.run_due()
        step.refresh_from_db()
        self.assertEqual(step.status, 'sent')
        self.assertIsNotNone(step.sent_at)


class SendTests(_Base):
    def setUp(self):
        super().setUp()
        set_app_settings(self, 'post_purchase', **ALL_ON)
        # The store manages consent; this customer said yes to marketing at checkout.
        Order.objects.filter(pk=self.order.pk).update(
            metadata={'consent': {'managed': True, 'analytics': False, 'marketing': True}}
        )

    def test_delivered_followup_goes_to_the_order_address_from_a_template(self):
        from core.utils.site import store_name

        step = self.due('delivered_followup')
        self.run_due()
        [message] = self.sent('arrive')
        self.assertEqual(message.to, ['quillon@example.com'])
        self.assertIn(self.order.order_number, message.subject)
        self.assertIn(store_name(), message.body)
        self.assertNotIn('dot books', message.body)
        self.assertNotIn('List-Unsubscribe', message.extra_headers)
        step.refresh_from_db()
        self.assertEqual(step.status, 'sent')

    def test_a_late_step_is_skipped_not_sent(self):
        step = self.due('delivered_followup', ago=timedelta(days=4))
        self.run_due()
        self.assertEqual(mail.outbox, [])
        step.refresh_from_db()
        self.assertEqual((step.status, step.error), ('skipped', 'late'))

    def test_a_step_switched_off_is_skipped(self):
        set_app_settings(self, 'post_purchase', review_request_enabled=False)
        step = self.due('review_request')
        self.run_due()
        self.assertEqual(mail.outbox, [])
        step.refresh_from_db()
        self.assertEqual((step.status, step.error), ('skipped', 'switched off'))

    def test_a_queued_tracking_step_is_skipped(self):
        step = self.due('tracking_sent')
        self.run_due()
        self.assertEqual(mail.outbox, [])
        step.refresh_from_db()
        self.assertEqual(step.status, 'skipped')

    def test_a_cancelled_order_gets_nothing(self):
        Order.objects.filter(pk=self.order.pk).update(status='cancelled')
        step = self.due('delivered_followup')
        self.run_due()
        self.assertEqual(mail.outbox, [])
        step.refresh_from_db()
        self.assertEqual((step.status, step.error), ('skipped', 'order cancelled'))

    def test_an_exchange_order_gets_nothing(self):
        Order.objects.filter(pk=self.order.pk).update(
            metadata={
                'exchange_of': 'RMA-1',
                'consent': {'managed': True, 'analytics': False, 'marketing': True},
            }
        )
        step = self.due('review_request')
        self.run_due()
        self.assertEqual(mail.outbox, [])
        step.refresh_from_db()
        self.assertEqual((step.status, step.error), ('skipped', 'exchange order'))

    def test_review_request_links_each_product_with_campaign_tags(self):
        self.due('review_request')
        self.run_due()
        [message] = self.sent('How was')
        body = self.body(message)
        self.assertIn('Zephyr Atlas', body)
        self.assertIn('/reviews/add/', body)
        self.assertIn('utm_source=post_purchase', body)
        self.assertIn('utm_medium=email', body)
        self.assertIn('utm_campaign=review_request', body)

    def test_marketing_carries_the_one_click_unsubscribe_pair(self):
        self.due('review_request')
        self.run_due()
        [message] = self.sent('How was')
        self.assertIn('/post-purchase/unsubscribe/', message.extra_headers['List-Unsubscribe'])
        self.assertEqual(
            message.extra_headers['List-Unsubscribe-Post'], 'List-Unsubscribe=One-Click'
        )
        self.assertIn('/post-purchase/unsubscribe/', message.body)

    def test_nps_link_is_on_the_store_and_tagged(self):
        from core.utils.site import site_base_url

        self.due('nps_survey')
        self.run_due()
        [message] = self.sent('survey')
        self.assertIn(f'{site_base_url().rstrip("/")}/post-purchase/nps/', message.body)
        self.assertIn('utm_campaign=nps_survey', message.body)

    def test_marketing_without_consent_is_skipped(self):
        Order.objects.filter(pk=self.order.pk).update(
            metadata={'consent': {'managed': True, 'analytics': True, 'marketing': False}}
        )
        review = self.due('review_request')
        delivered = self.due('delivered_followup')
        self.run_due()
        self.assertEqual(len(mail.outbox), 1)
        review.refresh_from_db()
        delivered.refresh_from_db()
        self.assertEqual((review.status, review.error), ('skipped', 'no consent'))
        self.assertEqual(delivered.status, 'sent')

    def test_marketing_with_consent_is_sent(self):
        Order.objects.filter(pk=self.order.pk).update(
            metadata={'consent': {'managed': True, 'analytics': False, 'marketing': True}}
        )
        self.due('review_request')
        self.run_due()
        self.assertEqual(len(self.sent('How was')), 1)

    def test_an_address_that_opted_out_gets_no_marketing(self):
        from plugins.installed.post_purchase.models import JourneyOptOut

        JourneyOptOut.objects.create(email='quillon@example.com')
        review = self.due('review_request')
        self.due('delivered_followup')
        self.run_due()
        self.assertEqual(len(mail.outbox), 1)
        review.refresh_from_db()
        self.assertEqual((review.status, review.error), ('skipped', 'opted out'))

    def test_templates_compile(self):
        for key in ('post_purchase_delivered', 'post_purchase_review', 'post_purchase_nps'):
            for ext in ('html', 'txt'):
                with self.subTest(template=f'{key}.{ext}'):
                    get_template(f'emails/{key}.{ext}')

    def test_disabled_app_sends_nothing(self):
        from plugins.registry import app_registry

        self.due('delivered_followup')
        app_registry.deactivate('post_purchase')
        self.addCleanup(app_registry.activate, 'post_purchase')

        # The beat entry still fires the task by name; an app that is off sends nothing.
        self.run_due()
        self.assertEqual(mail.outbox, [])


class UnsubscribeTests(_Base):
    def url(self, email='Quillon@Example.com'):
        from plugins.installed.post_purchase.unsubscribe import unsubscribe_url

        return unsubscribe_url(email)

    def test_get_asks_and_records_nothing(self):
        from plugins.installed.post_purchase.models import JourneyOptOut

        response = self.client.get(self.url())
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'<form method="post"', response.content)
        self.assertFalse(JourneyOptOut.objects.exists())

    def test_post_records_the_address_once(self):
        from plugins.installed.post_purchase.models import JourneyOptOut

        for _ in range(2):
            response = self.client.post(self.url())
            self.assertEqual(response.status_code, 200)
        self.assertEqual(
            list(JourneyOptOut.objects.values_list('email', flat=True)), ['quillon@example.com']
        )

    def test_one_click_post_needs_no_csrf_token(self):
        from django.test import Client

        response = Client(enforce_csrf_checks=True).post(
            self.url(), {'List-Unsubscribe': 'One-Click'}
        )
        self.assertEqual(response.status_code, 200)

    def test_a_forged_token_is_refused(self):
        from plugins.installed.post_purchase.models import JourneyOptOut

        response = self.client.post('/post-purchase/unsubscribe/forged/')
        self.assertEqual(response.status_code, 404)
        self.assertFalse(JourneyOptOut.objects.exists())
