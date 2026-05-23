"""Affiliates plugin manifest."""
from __future__ import annotations

from morpheus import events
from morpheus import Plugin, SettingsPanel


class AffiliatesPlugin(Plugin):
    name = 'affiliates'
    label = 'Affiliate Platform'
    version = '0.1.0'
    description = 'Affiliate links, attribution, conversions, payouts.'
    has_models = True
    requires = ['orders', 'customers']

    def ready(self) -> None:
        self.register_graphql_extension('plugins.installed.affiliates.graphql.queries')
        self.register_urls('plugins.installed.affiliates.urls', prefix='', namespace='affiliates')
        self.register_hook(events.ORDER_PLACED, self.on_order_placed, priority=70)
        # Refund clawback. ORDER_CANCELLED fires today; PAYMENT_REFUNDED
        # is defined but not yet emitted by the orders plugin — wire it
        # here too so we plug in automatically when orders starts
        # firing it.
        self.register_hook(events.ORDER_CANCELLED, self.on_order_refunded, priority=70)
        if hasattr(events, 'PAYMENT_REFUNDED'):
            self.register_hook(events.PAYMENT_REFUNDED, self.on_order_refunded, priority=70)

    def on_order_placed(self, order, **kwargs):
        """Attribute an affiliate to a freshly-placed order.

        Two attribution signals (in priority):
          1. ``shipping_address.affiliate_code`` — set by the
             storefront when the ``morph_aff`` cookie was present.
          2. ``order.source`` of the form ``affiliate:<code>``.
          3. The order's coupon code (Phase A1.5) — if it matches
             an ``AffiliateLink.coupon_code`` we attribute even
             without a click. This is how influencer shout-outs
             work in 2026.
        """
        code = ''
        if getattr(order, 'shipping_address', None):
            code = order.shipping_address.get('affiliate_code', '') if isinstance(order.shipping_address, dict) else ''
        if not code and getattr(order, 'source', '').startswith('affiliate:'):
            code = order.source.split(':', 1)[1]

        # Coupon attribution fallback. Pull from order.coupon_code or
        # order.metadata.coupon_code depending on what the cart wrote.
        coupon = (getattr(order, 'coupon_code', '') or '').strip()
        if not coupon and isinstance(getattr(order, 'metadata', None), dict):
            coupon = (order.metadata.get('coupon_code') or '').strip()

        if not code and not coupon:
            return
        from plugins.installed.affiliates.services import attribute_order
        attribute_order(order=order, affiliate_code=code, coupon_code=coupon)

    def on_order_refunded(self, order, **kwargs):
        """Reverse any affiliate conversion attached to a refunded
        order. See ``services.clawback_on_refund`` for the policy."""
        from plugins.installed.affiliates.services import clawback_on_refund
        try:
            clawback_on_refund(order=order)
        except Exception as exc:  # noqa: BLE001 — never block refund processing
            import logging
            logging.getLogger('morpheus.affiliates').warning(
                'clawback failed for order %s: %s', getattr(order, 'pk', '?'), exc,
            )

    def contribute_agent_tools(self) -> list:
        from plugins.installed.affiliates.agent_tools import (
            create_affiliate_tool, list_affiliates_tool,
            mark_payout_paid_tool, pending_payouts_tool,
        )
        return [
            list_affiliates_tool, pending_payouts_tool,
            mark_payout_paid_tool, create_affiliate_tool,
        ]

    def contribute_settings_panel(self) -> SettingsPanel:
        return SettingsPanel(
            label='Affiliates',
            description='Default program rules and payout policy. New AffiliateProgram rows inherit these defaults.',
            schema=self.get_config_schema(),
            category='marketing',
        )

    def get_config_schema(self) -> dict:
        return {
            'type': 'object',
            'properties': {
                'default_commission_percent': {
                    'type': 'number',
                    'title': 'Default commission %',
                    'description': 'Percentage of order subtotal an affiliate earns by default.',
                    'default': 10,
                },
                'cookie_window_days': {
                    'type': 'integer',
                    'title': 'Cookie window (days)',
                    'description': 'How long an affiliate click remains attributable. 30 is industry standard.',
                    'default': 30,
                },
                'min_payout_threshold': {
                    'type': 'number',
                    'title': 'Minimum payout threshold',
                    'description': 'Affiliates must accrue at least this much before a payout is generated.',
                    'default': 25,
                },
                'auto_lock_days': {
                    'type': 'integer',
                    'title': 'Refund clawback window (days)',
                    'description': 'After this many days a conversion is locked in and survives any refund.',
                    'default': 30,
                },
                'allow_self_signup': {
                    'type': 'boolean',
                    'title': 'Allow public affiliate sign-up',
                    'description': 'When off, only the merchant can create affiliates via the dashboard.',
                    'default': True,
                },
            },
        }

    def contribute_dashboard_pages(self) -> list:
        # nav='hidden' because base.html now renders the Affiliates +
        # Payouts links explicitly in the main sidebar (with the
        # parent/child shape the merchant expects). The DashboardPage
        # rows are still registered so the plugin_page_router resolves
        # the URLs at /dashboard/apps/affiliates/list/ and
        # /dashboard/apps/affiliates/payouts/.
        from morpheus import DashboardPage
        return [
            DashboardPage(
                label='Affiliates', slug='list',
                view='plugins.installed.affiliates.dashboard.affiliates_list',
                icon='link', section='growth', order=10, nav='hidden',
            ),
            DashboardPage(
                label='Payouts', slug='payouts',
                view='plugins.installed.affiliates.dashboard.payouts_list',
                icon='wallet', section='growth', order=20, nav='hidden',
            ),
        ]
