"""The dashboard-home activity feed is CONTRIBUTED by the owning plugins via
the ACTIVITY_FEED filter, NOT hardcoded in admin_dashboard. So disabling
reviews / loyalty_points / crm makes their feed entries vanish, instead of
the dashboard querying a disabled plugin's models behind the merchant's back.
"""

# Lazy imports inside test methods are intentional (plugin load-order isolation).
# ruff: noqa: PLC0415
from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.test import TestCase
from djmoney.money import Money

_HOME_PY = Path(settings.BASE_DIR) / 'plugins/installed/admin_dashboard/views_split/home.py'


class ActivityFeedModularityTests(TestCase):
    def test_feed_no_longer_imports_sibling_plugin_models(self):
        # Scope to the _compute_activity_feed function body — the KPI tiles
        # above it still query orders/catalog directly; migrating those is a
        # separate increment.
        src = _HOME_PY.read_text(encoding='utf-8')
        start = src.index('def _compute_activity_feed')
        end = src.index('\ndef ', start + 1)
        body = src[start:end]
        for plugin in ('orders', 'agent_core', 'catalog', 'loyalty_points', 'crm'):
            self.assertNotIn(
                f'installed.{plugin}',
                body,
                f'_compute_activity_feed still imports {plugin} — '
                "it belongs in that plugin's ACTIVITY_FEED subscriber",
            )

    def test_contributing_plugins_are_subscribed(self):
        # Wiring guard: every feed source registers on the ACTIVITY_FEED filter.
        from morpheus.core import MorpheusEvents, hook_registry

        quals = {
            getattr(hook_registry._unpack(entry)[1], '__qualname__', '')
            for entry in hook_registry._handlers.get(MorpheusEvents.ACTIVITY_FEED, [])
        }
        for plugin_cls in (
            'OrdersPlugin',
            'AgentCorePlugin',
            'ReviewsPlugin',
            'LoyaltyPointsPlugin',
            'CrmPlugin',
        ):
            self.assertTrue(any(plugin_cls in q for q in quals), f'{plugin_cls} not subscribed')

    def test_order_activity_contributed_end_to_end(self):
        from plugins.installed.admin_dashboard.views_split.home import _compute_activity_feed
        from plugins.installed.orders.models import Order

        order = Order.objects.create(
            email='c@example.com',
            subtotal=Money(Decimal('10'), 'USD'),
            total=Money(Decimal('10'), 'USD'),
        )
        order.confirm()  # logs an OrderEvent the orders subscriber picks up

        items = _compute_activity_feed(limit=10)
        order_items = [it for it in items if it['kind'] == 'order']
        self.assertTrue(order_items, 'order event missing from activity feed')
        self.assertIn(order.order_number, order_items[0]['label'])

    def test_newsletter_activity_contributed_end_to_end(self):
        from plugins.installed.admin_dashboard.views_split.home import _compute_activity_feed
        from plugins.installed.crm.models import Lead

        Lead.objects.create(email='reader@example.com', source='newsletter')

        items = _compute_activity_feed(limit=10)
        labels = [it['label'] for it in items if it['kind'] == 'newsletter']
        self.assertIn('Newsletter signup: reader@example.com', labels)

    def test_feed_sorted_newest_first_and_capped(self):
        from plugins.installed.admin_dashboard.views_split.home import _compute_activity_feed
        from plugins.installed.orders.models import Order

        for _i in range(4):
            order = Order.objects.create(
                email='c@example.com',
                subtotal=Money(Decimal('10'), 'USD'),
                total=Money(Decimal('10'), 'USD'),
            )
            order.confirm()

        items = _compute_activity_feed(limit=3)
        self.assertEqual(len(items), 3)
        whens = [it['when'] for it in items]
        self.assertEqual(whens, sorted(whens, reverse=True))

    def test_item_with_missing_when_is_dropped_not_500(self):
        # ACTIVITY_FEED is an open plugin contract: a contributed item with a
        # None timestamp must be dropped, never crash the sort (and the home
        # page) with a TypeError.
        from morpheus.core import MorpheusEvents, hook_registry
        from plugins.installed.admin_dashboard.views_split.home import _compute_activity_feed

        def _bad(value, limit=20, **kwargs):
            value.append({'kind': 'x', 'icon': 'bug', 'label': 'no-when', 'url': '/', 'when': None})
            return value

        hook_registry.register(MorpheusEvents.ACTIVITY_FEED, _bad, priority=1)
        try:
            items = _compute_activity_feed(limit=10)  # must not raise
        finally:
            hook_registry._handlers[MorpheusEvents.ACTIVITY_FEED] = [
                e for e in hook_registry._handlers[MorpheusEvents.ACTIVITY_FEED] if e[1] is not _bad
            ]
        self.assertNotIn('no-when', [it['label'] for it in items])
