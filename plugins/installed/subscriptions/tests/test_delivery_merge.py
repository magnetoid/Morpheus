"""The subscriptions_plus merge (2026-07-16): ONE Subscription model owns both
billing ('plan' kind) and delivery ('replenish'/'curated') subscriptions —
the parallel subscriptions_plus.Subscription is gone. Lines, shipments, and
the pause/skip/swap event log now FK the owner."""

# ruff: noqa: PLC0415
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.template.loader import get_template
from django.test import TestCase
from django.utils import timezone
from djmoney.money import Money

from plugins.installed.catalog.models import Product, ProductVariant
from plugins.installed.subscriptions.models import (
    Plan,
    Subscription,
    SubscriptionEvent,
    SubscriptionLine,
    SubscriptionShipment,
)


class DeliverySubscriptionTests(TestCase):
    def setUp(self):
        self.customer = get_user_model().objects.create_user(
            username='sub-c', email='sub@x.test', password='pw'
        )
        self.plan = Plan.objects.create(
            name='Monthly box',
            slug='monthly-box',
            price=Money(Decimal('25.00'), 'USD'),
            interval='month',
        )
        product = Product.objects.create(
            name='Box Book', slug='box-book', sku='BB1', price=Money(Decimal('25.00'), 'USD')
        )
        self.variant = ProductVariant.objects.create(
            product=product, name='Paperback', sku='BB1-PB', price=Money(Decimal('25.00'), 'USD')
        )

    def test_one_model_carries_billing_and_delivery(self):
        ship_at = timezone.now() + timedelta(days=30)
        sub = Subscription.objects.create(
            customer=self.customer,
            plan=self.plan,
            kind='replenish',
            cadence_days=30,
            next_ship_at=ship_at,
        )
        SubscriptionLine.objects.create(subscription=sub, variant=self.variant, quantity=2)
        SubscriptionShipment.objects.create(subscription=sub, ship_at=ship_at)
        SubscriptionEvent.objects.create(subscription=sub, kind='created')

        sub.refresh_from_db()
        self.assertEqual(sub.kind, 'replenish')
        self.assertEqual(sub.lines.count(), 1)
        self.assertEqual(sub.shipments.first().state, 'scheduled')
        self.assertEqual(sub.events.first().kind, 'created')
        # Billing spine intact — same row still belongs to a Plan.
        self.assertEqual(sub.plan.slug, 'monthly-box')

    def test_plain_billing_subscription_defaults(self):
        sub = Subscription.objects.create(customer=self.customer, plan=self.plan)
        self.assertEqual(sub.kind, 'plan')
        self.assertEqual(sub.cadence_days, 0)
        self.assertIsNone(sub.next_ship_at)

    def test_no_parallel_subscription_plugin_remains(self):
        from django.conf import settings as dj_settings

        self.assertNotIn('plugins.installed.subscriptions_plus', dj_settings.MORPHEUS_DEFAULT_APPS)
        with self.assertRaises(ImportError):
            import plugins.installed.subscriptions_plus  # noqa: F401

    def test_absorbed_subscribe_save_block_compiles(self):
        get_template('subscriptions/blocks/subscribe_save.html')
